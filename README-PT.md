<div align="center">

# AWS ECS Capacity Inventory - Analisador Multi-Conta

![AWS ECS](https://img.icons8.com/color/96/amazon-web-services.png)
![Python](https://img.icons8.com/color/96/python.png)

**Atualizado: 19 de Janeiro de 2026**

[![Follow @nicoleepaixao](https://img.shields.io/github/followers/nicoleepaixao?label=Follow&style=social)](https://github.com/nicoleepaixao)
[![Star this repo](https://img.shields.io/github/stars/nicoleepaixao/aws-ecs-capacity-inventory?style=social)](https://github.com/nicoleepaixao/aws-ecs-capacity-inventory)

<p align="center">
  <a href="README-PT.md">🇧🇷</a>
  <a href="README.md">🇺🇸</a>
</p>

</div>

---

## **O Problema**

Gerenciar capacidade ECS em múltiplas contas AWS é um desafio constante. Sua API de produção está lenta, mas você não sabe se é gargalo de CPU ou memória. Aquele microsserviço legado de seis meses atrás está queimando orçamento com 5% de utilização, mas ninguém quer mexer nele. Você gasta horas toda semana pulando entre consoles AWS, diferentes namespaces do CloudWatch e planilhas tentando responder perguntas simples: Quais serviços estão superdimensionados? Onde estão os gargalos? Podemos reduzir custos sem impactar a performance?

O planejamento de capacidade tradicional requer análise manual entre contas, correlacionando configurações ECS com métricas do CloudWatch, e traduzindo números brutos em insights acionáveis. Você precisa de algo que entenda ECS profundamente, fale AWS nativamente, e dê recomendações claras—não apenas dumps de dados.

---

## **A Solução**

Este script Python fornece **análise automatizada de capacidade** em todos os seus serviços ECS e contas AWS. Ele combina dados de configuração ECS com métricas do CloudWatch para entregar o que você realmente precisa: insights claros e acionáveis sobre sua infraestrutura.

**O que o torna diferente:**

✅ **Multi-conta nativo** - Analisa múltiplos perfis AWS em uma única execução  
✅ **Integração inteligente com CloudWatch** - Tenta Container Insights automaticamente, faz fallback para métricas ECS padrão  
✅ **Classificação inteligente** - Categoriza cada serviço como utilização baixo/medio/alto  
✅ **Recomendações acionáveis** - Orientação específica para cada padrão de serviço  
✅ **Output pronto para produção** - CSV completo para análise mais resumo no console para vitórias rápidas  
✅ **Zero dependências** - Apenas Python 3.9+ e boto3

---

## **Funcionalidades**

### **Coleta Abrangente de Dados**

Para cada serviço ECS, o script coleta:

- Detalhes da task definition (CPU units, memória em MB, convertidos para vCPU/GB)
- Estratégia de capacity provider (FARGATE, FARGATE_SPOT, EC2)
- Estado do serviço (contagem de tasks desired, running, pending)
- Utilização de CPU e memória do CloudWatch (janela de tempo configurável)
- Rastreamento da fonte de métricas (Container Insights vs namespace ECS padrão)

### **Classificação Inteligente**

**Níveis de CPU:**
- **baixo** (< 40%) - Superdimensionado, potencial economia de custos
- **medio** (40-69%) - Faixa de utilização ótima
- **alto** (≥ 70%) - Potencial gargalo, risco de performance
- **sem_dado** - Métricas não disponíveis

**Níveis de Memória:**
- **baixo** (< 35%) - Superdimensionado
- **medio** (35-69%) - Faixa saudável
- **alto** (≥ 70%) - Zona de perigo de OOMKill
- **sem_dado** - Métricas ausentes

### **Recomendações Baseadas em Padrões**

O script reconhece padrões comuns e fornece orientação específica:

| **Padrão** | **Recomendação** |
|-------------|-------------------|
| CPU alto + Mem baixo/medio | Aumentar CPU, habilitar autoscaling |
| Mem alto | Aumentar memória, investigar leaks |
| CPU baixo + Mem baixo | Redimensionar ou mudar para FARGATE_SPOT |
| CPU baixo + Mem medio/alto | Reduzir CPU, manter memória |
| Running = 0 | Revisar se serviço pode ser desativado |
| sem_dado | Habilitar Container Insights, validar métricas |

---

## **Instalação**

### **Pré-requisitos**

- Python 3.9 ou superior
- AWS CLI configurado com profiles
- boto3 instalado

### **Configuração Rápida**

```bash
# Clone o repositório
git clone https://github.com/nicoleepaixao/aws-ecs-capacity-inventory.git
cd aws-ecs-capacity-inventory

# Instale as dependências
pip install boto3 --break-system-packages

# Verifique os profiles AWS
aws configure list-profiles
```

---

## **Uso**

### **Análise de Profile Único**

```bash
python3 ecs_cluster_inventory.py \
  --profile company-dev \
  --region us-east-1 \
  --output ecs_enriched.csv
```

### **Análise Multi-Profile (Recomendado)**

```bash
python3 ecs_cluster_inventory.py \
  --profiles company-dev,company-staging,company-prod \
  --region us-east-1 \
  --output ecs_enriched.csv
```

### **Usando Arquivo de Profiles**

Crie `profiles.txt`:
```text
company-dev
company-staging
company-prod
# Comentários são ignorados
```

Execute:
```bash
python3 ecs_cluster_inventory.py \
  --profiles-file profiles.txt \
  --region us-east-1 \
  --output ecs_enriched.csv
```

### **Filtrar Clusters Específicos**

```bash
python3 ecs_cluster_inventory.py \
  --profiles company-dev,company-prod \
  --region us-east-1 \
  --clusters api-cluster,worker-cluster \
  --output ecs_enriched.csv
```

### **Janela de Tempo Customizada**

```bash
# Analise os últimos 7 dias
python3 ecs_cluster_inventory.py \
  --profile company-prod \
  --region us-east-1 \
  --hours 168 \
  --output ecs_enriched.csv
```

### **Thresholds Customizados**

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

## **Opções de Linha de Comando**

| **Opção** | **Descrição** | **Padrão** |
|-----------|-----------------|-------------|
| `--profile` | Nome de um único profile AWS | - |
| `--profiles` | Lista de profiles separados por vírgula | - |
| `--profiles-file` | Arquivo com profiles (um por linha) | - |
| `--region` | Região AWS (obrigatório) | - |
| `--output` | Caminho do arquivo CSV de saída | `ecs_enriched.csv` |
| `--clusters` | Filtrar por nomes de clusters (separados por vírgula) | Todos os clusters |
| `--hours` | Janela de tempo para métricas em horas | `24` |
| `--cpu-low-max` | Threshold de CPU para "baixo" (%) | `40` |
| `--cpu-med-max` | Threshold de CPU para "medio" (%) | `69` |
| `--mem-low-max` | Threshold de memória para "baixo" (%) | `35` |
| `--mem-med-max` | Threshold de memória para "medio" (%) | `69` |
| `--top` | Número de serviços no resumo | `10` |

---

## **Output**

### **Exportação CSV**

O script gera um CSV completo com estas colunas:

| **Coluna** | **Descrição** |
|-----------|-----------------|
| `account_id` | Nome do profile AWS |
| `region` | Região AWS |
| `cluster` | Nome do cluster ECS |
| `service` | Nome do serviço ECS |
| `task_definition_arn` | ARN da task definition |
| `cpu_units` | CPU units (1024 = 1 vCPU) |
| `vcpu` | vCPUs calculados |
| `memory_mb` | Memória em MB |
| `memory_gb` | Memória em GB |
| `capacity_providers` | Estratégia de capacity provider |
| `desired` | Contagem de tasks desejadas |
| `running` | Contagem de tasks rodando |
| `pending` | Contagem de tasks pendentes |
| `cpu_pct` | Utilização média de CPU (%) |
| `cpu_level` | Classificação de CPU |
| `mem_pct` | Utilização média de memória (%) |
| `mem_level` | Classificação de memória |
| `recommendation` | Recomendação de otimização |
| `metrics_source` | Namespace do CloudWatch usado |
| `error` | Mensagem de erro se aplicável |

### **Resumo no Console**

Exemplo de output:

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

## **Estratégia de Métricas do CloudWatch**

O script usa uma abordagem inteligente de fallback para coleta de métricas:

### **1. ECS/ContainerInsights (Preferido)**

Métricas mais precisas a nível de container, melhor para workloads Fargate:
- Métricas: `CpuUtilization`, `MemoryUtilization`
- Dimensões: `ClusterName`, `ServiceName`

### **2. AWS/ECS (Fallback)**

Namespace padrão disponível por default:
- Métricas: `CPUUtilization`, `MemoryUtilization`
- Dimensões: `ClusterName`, `ServiceName`

### **Seleção de Período**

O script ajusta automaticamente os períodos de consulta:

| **Janela de Tempo** | **Período** |
|-----------------|-----------|
| ≤ 6 horas | 60 segundos |
| 6-48 horas | 300 segundos |
| > 48 horas | 900 segundos |

---

## **Exemplos Práticos**

### **Exemplo 1: Check Diário de Produção**

```bash
python3 ecs_cluster_inventory.py \
  --profile company-prod \
  --region us-east-1 \
  --hours 24 \
  --output daily.csv
```

### **Exemplo 2: Planejamento Semanal de Capacidade**

```bash
python3 ecs_cluster_inventory.py \
  --profiles company-dev,company-staging,company-prod \
  --region us-east-1 \
  --hours 168 \
  --output weekly.csv
```

### **Exemplo 3: Otimização de Custos**

```bash
python3 ecs_cluster_inventory.py \
  --profiles company-prod \
  --region us-east-1 \
  --hours 72 \
  --cpu-low-max 30 \
  --mem-low-max 30 \
  --output cost_optimization.csv
```

### **Exemplo 4: Análise de Clusters Específicos**

```bash
python3 ecs_cluster_inventory.py \
  --profile company-prod \
  --region us-east-1 \
  --clusters production-cluster,api-cluster \
  --hours 48 \
  --output cluster_analysis.csv
```

---

## **Melhores Práticas**

### **Frequência de Análise**

✅ **Diária** - Check rápido de 24 horas para gargalos de produção  
✅ **Semanal** - Análise de 7 dias para planejamento de capacidade  
✅ **Mensal** - Análise estendida para identificação de tendências  
✅ **Antes de escalar** - Validar capacidade atual antes de mudanças

### **Ajuste de Thresholds**

```bash
# Conservador (captura mais problemas)
--cpu-low-max 50 --cpu-med-max 75 --mem-low-max 40 --mem-med-max 75

# Agressivo (maximiza utilização)
--cpu-low-max 35 --cpu-med-max 65 --mem-low-max 30 --mem-med-max 65
```

### **Habilitar Container Insights**

```bash
# Habilitar para cluster existente
aws ecs update-cluster-settings \
  --cluster production-cluster \
  --settings name=containerInsights,value=enabled

# Habilitar por padrão para novos clusters
aws ecs put-account-setting \
  --name containerInsights \
  --value enabled
```

---

## **Troubleshooting**

| **Erro** | **Solução** |
|----------|-------------|
| `Profile not found` | Execute `aws configure --profile NOME` |
| `Access Denied` | Adicione as permissões IAM necessárias (veja abaixo) |
| `No metrics found` | Habilite Container Insights ou aguarde 24h |
| `sem_dado for all services` | Verifique permissões IAM para CloudWatch |
| `Connection timeout` | Verifique credenciais AWS e conectividade de rede |

### **Permissões IAM Necessárias**

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

## **Exemplos de Integração**

### **Análise Agendada (Cron)**

```bash
# Adicione ao crontab para análise diária
0 8 * * * cd /path/to/repo && python3 ecs_cluster_inventory.py \
  --profiles-file profiles.txt \
  --region us-east-1 \
  --output /var/reports/ecs_daily_$(date +\%Y\%m\%d).csv
```

### **Notificações Slack**

```bash
#!/bin/bash
# analyze_and_notify.sh

python3 ecs_cluster_inventory.py \
  --profiles company-prod \
  --region us-east-1 \
  --output /tmp/ecs_analysis.csv

BOTTLENECKS=$(grep -c ",alto," /tmp/ecs_analysis.csv)

curl -X POST -H 'Content-type: application/json' \
  --data "{\"text\":\"Análise ECS: Encontrados $BOTTLENECKS potenciais gargalos\"}" \
  $SLACK_WEBHOOK_URL
```

---

## **Contribuindo**

Contribuições são bem-vindas! Por favor:

1. Faça um fork do repositório
2. Crie uma feature branch (`git checkout -b feature/funcionalidade-incrivel`)
3. Commit suas mudanças (`git commit -m 'feat: adiciona funcionalidade incrível'`)
4. Push para a branch (`git push origin feature/funcionalidade-incrivel`)
5. Abra um Pull Request

---

## **Licença**

Este projeto está licenciado sob a Licença MIT - veja o arquivo LICENSE para detalhes.

---

## **Projetos Relacionados**

- [AWS ECS Fargate Nginx OIDC Pipeline](https://github.com/nicoleepaixao/aws-ecs-fargate-nginx-oidc-pipeline) - Pipeline CI/CD seguro para ECS
- [AWS ECS Infrastructure Setup](https://github.com/nicoleepaixao/aws-ecs-fargate-nginx-awscli) - Deploy completo de infraestrutura

---

## **Conecte-se Comigo**

<div align="center">

[![GitHub](https://img.shields.io/badge/GitHub-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/nicoleepaixao)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-0077B5?logo=linkedin&logoColor=white&style=for-the-badge)](https://www.linkedin.com/in/nicolepaixao/)
[![Medium](https://img.shields.io/badge/Medium-12100E?style=for-the-badge&logo=medium&logoColor=white)](https://medium.com/@nicoleepaixao)

</div>

---

<div align="center">

**Otimize sua capacidade ECS com insights baseados em dados**

*Feito com ❤️ por [Nicole Paixão](https://github.com/nicoleepaixao)*

</div>
