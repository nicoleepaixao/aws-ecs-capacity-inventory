#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ecs_cluster_inventory.py

All-in-one script (AWS -> inventory -> classification) with MULTI-PROFILE support:
- Iterates through multiple AWS profiles (e.g., company-dev, company-prod, ...)
- Lists ECS clusters and services
- Collects task definition (cpu, memory)
- Collects service capacity providers
- Collects Desired/Running/Pending counts
- Fetches average CPU% and Memory% metrics from CloudWatch (trying:
    1) ECS/ContainerInsights (CpuUtilization/MemoryUtilization)
    2) AWS/ECS (CPUUtilization/MemoryUtilization)
  If no metrics exist, marks as "no_data".
- Classifies CPU and Memory: low / medium / high / no_data
- Generates recommendations
- Exports enriched CSV + prints summary

✅ Applied adjustments:
- "account_id" column = profile NAME (e.g., company-dev), not account number
- MEMORY thresholds:
    low: < 35%
    medium: 35% to 69%
    high: >= 70%

Requirements:
- Python 3.9+
- boto3 installed
- AWS profiles configured (aws configure / SSO etc.)

Examples:

1) Run for 1 profile:
python3 ecs_cluster_inventory.py --profile company-dev --region us-east-1 --output ecs_enriched.csv

2) Run multi-profile:
python3 ecs_cluster_inventory.py --profiles company-dev,company-staging,company-prod --region us-east-1 --output ecs_enriched.csv

3) Run reading profiles from file (1 per line):
python3 ecs_cluster_inventory.py --profiles-file profiles.txt --region us-east-1 --output ecs_enriched.csv

Optional:
--clusters api-cluster,worker-cluster
--hours 24
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

import boto3
from botocore.exceptions import BotoCoreError, ClientError


# -----------------------------
# Default thresholds (adjustable via CLI)
# -----------------------------
DEFAULT_CPU_LOW_MAX = 40.0
DEFAULT_CPU_MED_MAX = 69.0

# Memory: low up to 35%, medium 35-69%, high >= 70%
DEFAULT_MEM_LOW_MAX = 35.0
DEFAULT_MEM_MED_MAX = 69.0


# -----------------------------
# Helpers
# -----------------------------
def classify(value_pct: Optional[float], low_max: float, med_max: float) -> str:
    if value_pct is None:
        return "no_data"
    if value_pct < low_max:
        return "low"
    if value_pct <= med_max:
        return "medium"
    return "high"


def cpu_units_to_vcpu(cpu_units: Optional[int]) -> Optional[float]:
    if cpu_units is None:
        return None
    try:
        return float(cpu_units) / 1024.0
    except Exception:
        return None


def memory_mb_to_gb(memory_mb: Optional[int]) -> Optional[float]:
    if memory_mb is None:
        return None
    try:
        return float(memory_mb) / 1024.0
    except Exception:
        return None


def recommendation(cpu_level: str, mem_level: str, running: int) -> str:
    if running == 0:
        return "Running=0. Service has no running tasks: review if it can be deactivated/removed or kept on-demand."

    if cpu_level == "high" and mem_level in ("low", "medium"):
        return "High CPU: possible bottleneck. Consider increasing CPU and/or enabling autoscaling (keep memory)."

    if mem_level == "high":
        return "High memory (OOMKill risk). Consider increasing memory and investigate leak/cache/heap."

    if cpu_level == "low" and mem_level == "low":
        return "Low CPU and memory: over-provisioned. Consider downsizing CPU/memory and/or using FARGATE_SPOT."

    if cpu_level == "low" and mem_level in ("medium", "high"):
        return "Idle CPU: consider reducing CPU while maintaining memory."

    if cpu_level in ("medium", "high") and mem_level == "low":
        return "Idle memory: consider reducing memory (carefully) while maintaining CPU."

    if cpu_level == "no_data" or mem_level == "no_data":
        return "Incomplete metrics: validate Container Insights / ECS metrics in CloudWatch and re-evaluate."

    return "Looks OK: monitor peaks and adjust with historical data (7-14 days)."


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def chunks(lst: List[str], n: int) -> List[List[str]]:
    return [lst[i:i + n] for i in range(0, len(lst), n)]


def parse_int_maybe(v) -> Optional[int]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except Exception:
            return None


def arn_to_name(arn: str) -> str:
    if not arn:
        return ""
    if "/" in arn:
        return arn.split("/")[-1]
    return arn


# -----------------------------
# Data model
# -----------------------------
@dataclass
class ServiceRow:
    account_id: str          # profile name
    region: str
    cluster: str
    service: str
    task_definition_arn: str
    cpu_units: Optional[int]
    vcpu: Optional[float]
    memory_mb: Optional[int]
    memory_gb: Optional[float]
    capacity_providers: str
    desired: int
    running: int
    pending: int
    cpu_pct: Optional[float]
    mem_pct: Optional[float]
    cpu_level: str
    mem_level: str
    action: str


# -----------------------------
# AWS Collectors
# -----------------------------
def list_all_clusters(ecs) -> List[str]:
    arns: List[str] = []
    paginator = ecs.get_paginator("list_clusters")
    for page in paginator.paginate():
        arns.extend(page.get("clusterArns", []))
    return arns


def list_services_in_cluster(ecs, cluster_arn: str) -> List[str]:
    arns: List[str] = []
    paginator = ecs.get_paginator("list_services")
    for page in paginator.paginate(cluster=cluster_arn):
        arns.extend(page.get("serviceArns", []))
    return arns


def describe_services(ecs, cluster_arn: str, service_arns: List[str]) -> List[Dict]:
    out: List[Dict] = []
    for batch in chunks(service_arns, 10):  # describe_services supports up to 10
        resp = ecs.describe_services(cluster=cluster_arn, services=batch, include=["TAGS"])
        out.extend(resp.get("services", []))
    return out


def describe_task_definition(ecs, task_def_arn: str) -> Dict:
    return ecs.describe_task_definition(taskDefinition=task_def_arn).get("taskDefinition", {})


def capacity_providers_str(svc: Dict) -> str:
    cps = svc.get("capacityProviderStrategy") or []
    if not cps:
        return ""
    parts = []
    for cp in cps:
        name = cp.get("capacityProvider", "")
        weight = cp.get("weight", None)
        base = cp.get("base", None)
        if weight is None and base is None:
            parts.append(name)
        else:
            parts.append(f"{name}(weight={weight},base={base})")
    return ",".join(parts)


# -----------------------------
# CloudWatch Metrics
# -----------------------------
def get_metric_avg(
    cw,
    namespace: str,
    metric_name: str,
    dimensions: List[Dict[str, str]],
    start: dt.datetime,
    end: dt.datetime,
    period: int,
) -> Optional[float]:
    try:
        resp = cw.get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=dimensions,
            StartTime=start,
            EndTime=end,
            Period=period,
            Statistics=["Average"],
        )
        dps = resp.get("Datapoints", [])
        if not dps:
            return None
        dps.sort(key=lambda x: x.get("Timestamp"))
        vals = [dp["Average"] for dp in dps if "Average" in dp]
        if not vals:
            return None
        return float(sum(vals) / len(vals))
    except (ClientError, BotoCoreError):
        return None


def fetch_cpu_mem_pct(
    cw,
    cluster_name: str,
    service_name: str,
    start: dt.datetime,
    end: dt.datetime,
) -> Tuple[Optional[float], Optional[float], str]:
    total_seconds = (end - start).total_seconds()
    if total_seconds <= 6 * 3600:
        period = 60
    elif total_seconds <= 48 * 3600:
        period = 300
    else:
        period = 900

    dims = [{"Name": "ClusterName", "Value": cluster_name}, {"Name": "ServiceName", "Value": service_name}]

    # 1) ContainerInsights
    cpu = get_metric_avg(cw, "ECS/ContainerInsights", "CpuUtilization", dims, start, end, period)
    mem = get_metric_avg(cw, "ECS/ContainerInsights", "MemoryUtilization", dims, start, end, period)
    if cpu is not None or mem is not None:
        return cpu, mem, "ECS/ContainerInsights"

    # 2) AWS/ECS
    cpu = get_metric_avg(cw, "AWS/ECS", "CPUUtilization", dims, start, end, period)
    mem = get_metric_avg(cw, "AWS/ECS", "MemoryUtilization", dims, start, end, period)
    if cpu is not None or mem is not None:
        return cpu, mem, "AWS/ECS"

    return None, None, "no_data"


# -----------------------------
# Output
# -----------------------------
def write_csv(rows: List[ServiceRow], out_path: str) -> None:
    fields = [
        "account_id",
        "region",
        "cluster",
        "service",
        "task_definition_arn",
        "cpu_units",
        "vcpu",
        "memory_mb",
        "memory_gb",
        "capacity_providers",
        "desired",
        "running",
        "pending",
        "cpu_pct",
        "cpu_level",
        "mem_pct",
        "mem_level",
        "recommendation",
        "metrics_source",
        "error",
    ]

    out_f = sys.stdout if out_path == "-" else open(out_path, "w", encoding="utf-8", newline="")
    try:
        w = csv.DictWriter(out_f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "account_id": r.account_id,
                    "region": r.region,
                    "cluster": r.cluster,
                    "service": r.service,
                    "task_definition_arn": r.task_definition_arn,
                    "cpu_units": r.cpu_units if r.cpu_units is not None else "",
                    "vcpu": f"{r.vcpu:.2f}" if r.vcpu is not None else "",
                    "memory_mb": r.memory_mb if r.memory_mb is not None else "",
                    "memory_gb": f"{r.memory_gb:.2f}" if r.memory_gb is not None else "",
                    "capacity_providers": r.capacity_providers,
                    "desired": r.desired,
                    "running": r.running,
                    "pending": r.pending,
                    "cpu_pct": f"{r.cpu_pct:.2f}" if r.cpu_pct is not None else "",
                    "cpu_level": r.cpu_level,
                    "mem_pct": f"{r.mem_pct:.2f}" if r.mem_pct is not None else "",
                    "mem_level": r.mem_level,
                    "recommendation": r.action,
                    "metrics_source": getattr(r, "metrics_source", ""),
                    "error": getattr(r, "error", ""),
                }
            )
    finally:
        if out_path != "-":
            out_f.close()


def print_summary(rows: List[ServiceRow], top: int = 10) -> None:
    bottlenecks = [r for r in rows if r.running > 0 and (r.cpu_level == "high" or r.mem_level == "high")]
    oversized = [r for r in rows if r.running > 0 and r.cpu_level == "low" and r.mem_level == "low"]
    stopped = [r for r in rows if r.running == 0]

    def k_cpu(r: ServiceRow) -> float:
        return r.cpu_pct if r.cpu_pct is not None else -1.0

    def k_mem(r: ServiceRow) -> float:
        return r.mem_pct if r.mem_pct is not None else -1.0

    print("\n=== SUMMARY ===")
    print(f"Total services: {len(rows)}")
    print(f"Bottlenecks (high CPU or high memory, running>0): {len(bottlenecks)}")
    print(f"Over-provisioned (low CPU and low memory, running>0): {len(oversized)}")
    print(f"Running=0: {len(stopped)}")

    if bottlenecks:
        print("\n--- Top bottlenecks by CPU% ---")
        for r in sorted(bottlenecks, key=k_cpu, reverse=True)[:top]:
            print(f"{r.account_id} | {r.cluster}/{r.service} | CPU {r.cpu_pct}% ({r.cpu_level}) | Mem {r.mem_pct}% ({r.mem_level})")

        print("\n--- Top bottlenecks by Memory% ---")
        for r in sorted(bottlenecks, key=k_mem, reverse=True)[:top]:
            print(f"{r.account_id} | {r.cluster}/{r.service} | Mem {r.mem_pct}% ({r.mem_level}) | CPU {r.cpu_pct}% ({r.cpu_level})")

    if oversized:
        print("\n--- Top over-provisioned (low CPU + low memory) ---")
        for r in oversized[:top]:
            print(f"{r.account_id} | {r.cluster}/{r.service} | CPU {r.cpu_pct}% | Mem {r.mem_pct}%")

    if stopped:
        print("\n--- Running=0 (cleanup / on-demand candidates) ---")
        for r in stopped[:top]:
            print(f"{r.account_id} | {r.cluster}/{r.service} | desired={r.desired} running={r.running} pending={r.pending}")


# -----------------------------
# Multi-profile handling
# -----------------------------
DEFAULT_PROFILES = [
    "company-dev",
    "company-staging",
    "company-prod",
]


def parse_profiles(args) -> List[str]:
    if args.profiles:
        return [p.strip() for p in args.profiles.split(",") if p.strip()]
    if args.profiles_file:
        profs: List[str] = []
        with open(args.profiles_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                profs.append(line)
        return profs
    if args.profile:
        return [args.profile]
    # fallback default
    return list(DEFAULT_PROFILES)


def collect_for_profile(
    profile: str,
    region: str,
    start: dt.datetime,
    end: dt.datetime,
    args,
) -> List[ServiceRow]:
    rows: List[ServiceRow] = []

    try:
        session = boto3.Session(profile_name=profile, region_name=region)
        ecs = session.client("ecs")
        cw = session.client("cloudwatch")
    except Exception as e:
        print(f"[ERROR] Failed to create session for profile={profile}: {e}", file=sys.stderr)
        return rows

    account_id = profile  # profile name
    filter_names = [c.strip() for c in (args.clusters or "").split(",") if c.strip()]
    allow = set(filter_names) if filter_names else None

    try:
        cluster_arns = list_all_clusters(ecs)
    except Exception as e:
        print(f"[ERROR] list_clusters failed for profile={profile}: {e}", file=sys.stderr)
        return rows

    if allow:
        cluster_arns = [arn for arn in cluster_arns if arn_to_name(arn) in allow]

    for c_arn in cluster_arns:
        cluster_name = arn_to_name(c_arn)

        try:
            service_arns = list_services_in_cluster(ecs, c_arn)
        except Exception as e:
            print(f"[WARN] list_services failed for profile={profile} cluster={cluster_name}: {e}", file=sys.stderr)
            continue

        if not service_arns:
            continue

        try:
            services = describe_services(ecs, c_arn, service_arns)
        except Exception as e:
            print(f"[WARN] describe_services failed for profile={profile} cluster={cluster_name}: {e}", file=sys.stderr)
            continue

        for svc in services:
            svc_name = svc.get("serviceName", "")
            task_def_arn = svc.get("taskDefinition", "")

            desired = int(svc.get("desiredCount", 0) or 0)
            running = int(svc.get("runningCount", 0) or 0)
            pending = int(svc.get("pendingCount", 0) or 0)

            cap_prov = capacity_providers_str(svc)

            cpu_units = None
            memory_mb = None
            vcpu = None
            mem_gb = None

            try:
                td = describe_task_definition(ecs, task_def_arn) if task_def_arn else {}
                cpu_units = parse_int_maybe(td.get("cpu"))
                memory_mb = parse_int_maybe(td.get("memory"))
                vcpu = cpu_units_to_vcpu(cpu_units) if cpu_units is not None else None
                mem_gb = memory_mb_to_gb(memory_mb) if memory_mb is not None else None
            except Exception:
                pass

            cpu_pct, mem_pct, metrics_source = fetch_cpu_mem_pct(
                cw=cw,
                cluster_name=cluster_name,
                service_name=svc_name,
                start=start,
                end=end,
            )

            cpu_level = classify(cpu_pct, args.cpu_low_max, args.cpu_med_max)
            mem_level = classify(mem_pct, args.mem_low_max, args.mem_med_max)
            action = recommendation(cpu_level, mem_level, running)

            row = ServiceRow(
                account_id=account_id,
                region=region,
                cluster=cluster_name,
                service=svc_name,
                task_definition_arn=task_def_arn,
                cpu_units=cpu_units,
                vcpu=vcpu,
                memory_mb=memory_mb,
                memory_gb=mem_gb,
                capacity_providers=cap_prov,
                desired=desired,
                running=running,
                pending=pending,
                cpu_pct=cpu_pct,
                mem_pct=mem_pct,
                cpu_level=cpu_level,
                mem_level=mem_level,
                action=action,
            )
            setattr(row, "metrics_source", metrics_source)
            rows.append(row)

    return rows


# -----------------------------
# Main
# -----------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="ECS Inventory + CloudWatch (CPU/Mem %) + low/medium/high classification in a single multi-profile script."
    )

    parser.add_argument("--profile", help="Single AWS profile (e.g., company-dev)")
    parser.add_argument("--profiles", help="Comma-separated list of profiles (e.g., company-dev,company-prod,...)")
    parser.add_argument("--profiles-file", help="File with profiles (1 per line). Lines starting with # are ignored.")

    parser.add_argument("--region", required=True, help="AWS region (e.g., us-east-1)")
    parser.add_argument("--output", default="ecs_enriched.csv", help="Output CSV file (default: ecs_enriched.csv). Use '-' for stdout.")
    parser.add_argument("--clusters", default="", help="Optional: filter by clusters (comma-separated names).")
    parser.add_argument("--hours", type=int, default=24, help="Time window for metric averages (default: 24h)")
    parser.add_argument("--cpu-low-max", type=float, default=DEFAULT_CPU_LOW_MAX, help="CPU%% < this value => low (default 40)")
    parser.add_argument("--cpu-med-max", type=float, default=DEFAULT_CPU_MED_MAX, help="CPU%% <= this value => medium (default 69)")
    parser.add_argument("--mem-low-max", type=float, default=DEFAULT_MEM_LOW_MAX, help="Memory%% < this value => low (default 35)")
    parser.add_argument("--mem-med-max", type=float, default=DEFAULT_MEM_MED_MAX, help="Memory%% <= this value => medium (default 69)")
    parser.add_argument("--top", type=int, default=10, help="Number of services in summary (default 10)")
    args = parser.parse_args()

    profiles = parse_profiles(args)
    region = args.region

    end = utc_now()
    start = end - dt.timedelta(hours=max(1, args.hours))

    all_rows: List[ServiceRow] = []

    for prof in profiles:
        print(f"\n==> Collecting ECS data for profile: {prof} | region: {region}")
        rows = collect_for_profile(prof, region, start, end, args)
        all_rows.extend(rows)

    if not all_rows:
        print("No services found (or access failure).", file=sys.stderr)
        return 2

    write_csv(all_rows, args.output)
    print(f"\n✅ Enriched CSV generated at: {args.output}")
    print_summary(all_rows, top=args.top)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())