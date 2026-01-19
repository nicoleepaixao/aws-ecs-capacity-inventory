<div align="center">

# AWS ECS Capacity Inventory - Multi-Account Analyzer

![AWS ECS](https://img.icons8.com/color/96/amazon-web-services.png)
![Python](https://img.icons8.com/color/96/python.png)


**Updated: January 19, 2026**

[![Follow @nicoleepaixao](https://img.shields.io/github/followers/nicoleepaixao?label=Follow&style=social)](https://github.com/nicoleepaixao)
[![Star this repo](https://img.shields.io/github/stars/nicoleepaixao/aws-ecs-capacity-inventory?style=social)](https://github.com/nicoleepaixao/aws-ecs-capacity-inventory)

<p align="center">
  <a href="README-PT.md">🇧🇷</a>
  <a href="README.md">🇺🇸</a>
</p>

</div>

---

## **The Problem**

Managing ECS capacity across multiple AWS accounts is a constant challenge. Your production API is running slow, but you don't know if it's CPU-bound or memory-constrained. That legacy microservice from six months ago is burning through budget at 5% utilization, but nobody wants to touch it. You spend hours each week jumping between AWS consoles, different CloudWatch namespaces, and spreadsheets trying to answer simple questions: Which services are over-provisioned? Where are the bottlenecks? Can we reduce costs without impacting performance?

Traditional capacity planning requires manual analysis across accounts, correlating ECS configurations with CloudWatch metrics, and translating raw numbers into actionable insights. You need something that understands ECS deeply, speaks AWS natively, and gives you clear recommendations—not just data dumps.

---

## **The Solution**

This Python script provides **automated capacity analysis** across all your ECS services and AWS accounts. It combines ECS configuration data with CloudWatch metrics to deliver what you actually need: clear, actionable insights about your infrastructure.

**What makes it different:**

✅ **Multi-account native** - Analyze multiple AWS profiles in a single run  
✅ **Smart CloudWatch integration** - Automatically tries Container Insights, falls back to standard ECS metrics  
✅ **Intelligent classification** - Categorizes every service as baixo/medio/alto utilization  
✅ **Actionable recommendations** - Specific guidance for each service pattern  
✅ **Production-ready output** - Comprehensive CSV for analysis plus console summary for quick wins  
✅ **Zero dependencies** - Just Python 3.9+ and boto3

---

## **Features**

### **Comprehensive Data Collection**

For each ECS service, the script collects:

- Task definition details (CPU units, memory MB, converted to vCPU/GB)
- Capacity provider strategy (FARGATE, FARGATE_SPOT, EC2)
- Service state (desired, running, pending task counts)
- CloudWatch CPU and memory utilization (configurable time window)
- Metric source tracking (Container Insights vs standard ECS namespace)

### **Intelligent Classification**

**CPU Levels:**
- **baixo** (< 40%) - Over-provisioned, potential cost savings
- **medio** (40-69%) - Optimal utilization range
- **alto** (≥ 70%) - Potential bottleneck, performance risk
- **sem_dado** - No metrics available

**Memory Levels:**
- **baixo** (< 35%) - Over-provisioned
- **medio** (35-69%) - Healthy range
- **alto** (≥ 70%) - OOMKill danger zone
- **sem_dado** - Metrics missing

### **Pattern-Based Recommendations**

The script recognizes common patterns and provides specific guidance:

| **Pattern** | **Recommendation** |
|-------------|-------------------|
| CPU alto + Mem baixo/medio | Increase CPU, enable autoscaling |
| Mem alto | Increase memory, investigate leaks |
| CPU baixo + Mem baixo | Downsize or switch to FARGATE_SPOT |
| CPU baixo + Mem medio/alto | Reduce CPU, maintain memory |
| Running = 0 | Review if service can be deactivated |
| sem_dado | Enable Container Insights, validate metrics |

---

## **Installation**

### **Prerequisites**

- Python 3.9 or higher
- AWS CLI configured with profiles
- boto3 installed

### **Quick Setup**

```bash
# Clone the repository
git clone https://github.com/nicoleepaixao/aws-ecs-capacity-inventory.git
cd aws-ecs-capacity-inventory

# Install dependencies
pip install boto3 --break-system-packages

# Verify AWS profiles
aws configure list-profiles
```

---

## **Usage**

### **Single Profile Analysis**

```bash
python3 ecs_cluster_inventory.py \
  --profile company-dev \
  --region us-east-1 \
  --output ecs_enriched.csv
```

### **Multi-Profile Analysis (Recommended)**

```bash
python3 ecs_cluster_inventory.py \
  --profiles company-dev,company-staging,company-prod \
  --region us-east-1 \
  --output ecs_enriched.csv
```

### **Using Profiles File**

Create `profiles.txt`:
```text
company-dev
company-staging
company-prod
# Comments are ignored
```

Run:
```bash
python3 ecs_cluster_inventory.py \
  --profiles-file profiles.txt \
  --region us-east-1 \
  --output ecs_enriched.csv
```

### **Filter Specific Clusters**

```bash
python3 ecs_cluster_inventory.py \
  --profiles company-dev,company-prod \
  --region us-east-1 \
  --clusters api-cluster,worker-cluster \
  --output ecs_enriched.csv
```

### **Custom Time Window**

```bash
# Analyze last 7 days
python3 ecs_cluster_inventory.py \
  --profile company-prod \
  --region us-east-1 \
  --hours 168 \
  --output ecs_enriched.csv
```

### **Custom Thresholds**

```bash
python3 ecs_cluster_inventory.py \
  --profile company-prod \
  --region us-east-1 \
  --cpu-low-max 50 \
  --cpu-med-max 75 \
  --mem-low-max 40 \
  --mem-med-max 70 \
  --output ecs_enriched.csv
```

---

## **Command Line Options**

| **Option** | **Description** | **Default** |
|-----------|-----------------|-------------|
| `--profile` | Single AWS profile name | - |
| `--profiles` | Comma-separated list of profiles | - |
| `--profiles-file` | File with profiles (one per line) | - |
| `--region` | AWS region (required) | - |
| `--output` | Output CSV file path | `ecs_enriched.csv` |
| `--clusters` | Filter by cluster names (comma-separated) | All clusters |
| `--hours` | Time window for metrics in hours | `24` |
| `--cpu-low-max` | CPU threshold for "baixo" (%) | `40` |
| `--cpu-med-max` | CPU threshold for "medio" (%) | `69` |
| `--mem-low-max` | Memory threshold for "baixo" (%) | `35` |
| `--mem-med-max` | Memory threshold for "medio" (%) | `69` |
| `--top` | Number of services in summary | `10` |

---

## **Output**

### **CSV Export**

The script generates a comprehensive CSV with these columns:

| **Column** | **Description** |
|-----------|-----------------|
| `account_id` | AWS profile name |
| `region` | AWS region |
| `cluster` | ECS cluster name |
| `service` | ECS service name |
| `task_definition_arn` | Task definition ARN |
| `cpu_units` | CPU units (1024 = 1 vCPU) |
| `vcpu` | Calculated vCPUs |
| `memory_mb` | Memory in MB |
| `memory_gb` | Memory in GB |
| `capacity_providers` | Capacity provider strategy |
| `desired` | Desired task count |
| `running` | Running task count |
| `pending` | Pending task count |
| `cpu_pct` | Average CPU utilization (%) |
| `cpu_level` | CPU classification |
| `mem_pct` | Average memory utilization (%) |
| `mem_level` | Memory classification |
| `recommendation` | Optimization recommendation |
| `metrics_source` | CloudWatch namespace used |
| `error` | Error message if applicable |

### **Console Summary**

Example output:

```text
==> Coletando ECS para profile: company-prod | region: us-east-1

=== RESUMO ===
Total services: 47
Gargalos (CPU alto ou Mem alto, running>0): 8
Superdimensionados (CPU baixo e Mem baixo, running>0): 12
Running=0: 3

--- Top gargalos por CPU% ---
company-prod | production-cluster/api-service | CPU 89.45% (alto) | Mem 34.12% (baixo)
company-prod | production-cluster/worker-service | CPU 78.23% (alto) | Mem 68.90% (medio)

--- Top gargalos por Mem% ---
company-prod | production-cluster/cache-service | Mem 87.34% (alto) | CPU 23.45% (baixo)

--- Top superdimensionados (CPU baixo + Mem baixo) ---
company-prod | production-cluster/legacy-api | CPU 12.34% | Mem 18.90%

--- Running=0 (candidatos a cleanup / on-demand) ---
company-prod | production-cluster/backup-service | desired=0 running=0 pending=0

✅ CSV enriquecido gerado em: ecs_enriched.csv
```

---

## **CloudWatch Metrics Strategy**

The script uses an intelligent fallback approach for metric collection:

### **1. ECS/ContainerInsights (Preferred)**

More accurate container-level metrics, better for Fargate workloads:
- Metrics: `CpuUtilization`, `MemoryUtilization`
- Dimensions: `ClusterName`, `ServiceName`

### **2. AWS/ECS (Fallback)**

Standard namespace available by default:
- Metrics: `CPUUtilization`, `MemoryUtilization`
- Dimensions: `ClusterName`, `ServiceName`

### **Period Selection**

The script automatically adjusts query periods:

| **Time Window** | **Period** |
|-----------------|-----------|
| ≤ 6 hours | 60 seconds |
| 6-48 hours | 300 seconds |
| > 48 hours | 900 seconds |

---

## **Practical Examples**

### **Example 1: Daily Production Check**

```bash
python3 ecs_cluster_inventory.py \
  --profile company-prod \
  --region us-east-1 \
  --hours 24 \
  --output daily.csv
```

### **Example 2: Weekly Capacity Planning**

```bash
python3 ecs_cluster_inventory.py \
  --profiles company-dev,company-staging,company-prod \
  --region us-east-1 \
  --hours 168 \
  --output weekly.csv
```

### **Example 3: Cost Optimization**

```bash
python3 ecs_cluster_inventory.py \
  --profiles company-prod \
  --region us-east-1 \
  --hours 72 \
  --cpu-low-max 30 \
  --mem-low-max 30 \
  --output cost_optimization.csv
```

### **Example 4: Specific Cluster Analysis**

```bash
python3 ecs_cluster_inventory.py \
  --profile company-prod \
  --region us-east-1 \
  --clusters production-cluster,api-cluster \
  --hours 48 \
  --output cluster_analysis.csv
```

---

## **Best Practices**

### **Analysis Frequency**

✅ **Daily** - Quick 24-hour check for production bottlenecks  
✅ **Weekly** - 7-day analysis for capacity planning  
✅ **Monthly** - Extended analysis for trend identification  
✅ **Before scaling** - Validate current capacity before changes

### **Threshold Tuning**

```bash
# Conservative (catch more issues)
--cpu-low-max 50 --cpu-med-max 75 --mem-low-max 40 --mem-med-max 75

# Aggressive (maximize utilization)
--cpu-low-max 35 --cpu-med-max 65 --mem-low-max 30 --mem-med-max 65
```

### **Enable Container Insights**

```bash
# Enable for existing cluster
aws ecs update-cluster-settings \
  --cluster production-cluster \
  --settings name=containerInsights,value=enabled

# Enable by default for new clusters
aws ecs put-account-setting \
  --name containerInsights \
  --value enabled
```

---

## **Troubleshooting**

| **Error** | **Solution** |
|----------|-------------|
| `Profile not found` | Run `aws configure --profile NAME` |
| `Access Denied` | Add required IAM permissions (see below) |
| `No metrics found` | Enable Container Insights or wait 24h |
| `sem_dado for all services` | Check IAM permissions for CloudWatch |
| `Connection timeout` | Verify AWS credentials and network connectivity |

### **Required IAM Permissions**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecs:ListClusters",
        "ecs:ListServices",
        "ecs:DescribeServices",
        "ecs:DescribeTaskDefinition",
        "cloudwatch:GetMetricStatistics"
      ],
      "Resource": "*"
    }
  ]
}
```

---

## **Integration Examples**

### **Scheduled Analysis (Cron)**

```bash
# Add to crontab for daily analysis
0 8 * * * cd /path/to/repo && python3 ecs_cluster_inventory.py \
  --profiles-file profiles.txt \
  --region us-east-1 \
  --output /var/reports/ecs_daily_$(date +\%Y\%m\%d).csv
```

### **Slack Notifications**

```bash
#!/bin/bash
# analyze_and_notify.sh

python3 ecs_cluster_inventory.py \
  --profiles company-prod \
  --region us-east-1 \
  --output /tmp/ecs_analysis.csv

BOTTLENECKS=$(grep -c ",alto," /tmp/ecs_analysis.csv)

curl -X POST -H 'Content-type: application/json' \
  --data "{\"text\":\"ECS Analysis: Found $BOTTLENECKS potential bottlenecks\"}" \
  $SLACK_WEBHOOK_URL
```

---

## **Contributing**

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## **License**

This project is licensed under the MIT License - see the LICENSE file for details.

---

## **Related Projects**

- [AWS ECS Fargate Nginx OIDC Pipeline](https://github.com/nicoleepaixao/aws-ecs-fargate-nginx-oidc-pipeline) - Secure CI/CD pipeline for ECS
- [AWS ECS Infrastructure Setup](https://github.com/nicoleepaixao/aws-ecs-fargate-nginx-awscli) - Complete infrastructure deployment

---

## **Connect & Follow**

<div align="center">

[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/nicoleepaixao)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?logo=linkedin&logoColor=white&style=for-the-badge)](https://www.linkedin.com/in/nicolepaixao/)
[![Medium](https://img.shields.io/badge/Medium-12100E?style=for-the-badge&logo=medium&logoColor=white)](https://medium.com/@nicoleepaixao)

</div>

---

<div align="center">

**Optimize your ECS capacity with data-driven insights**

*Made with ❤️ by [Nicole Paixão](https://github.com/nicoleepaixao)*

</div>
