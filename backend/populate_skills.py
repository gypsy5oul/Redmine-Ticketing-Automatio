#!/usr/bin/env python3
"""
Populate Predefined Skills for DevOps Engineers
"""

import sys
sys.path.insert(0, '/app')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from loguru import logger

from app.core.config import settings
from app.models.team import Skill


# Predefined skills for DevOps engineers
PREDEFINED_SKILLS = [
    # Container & Orchestration
    {
        "name": "Kubernetes",
        "category": "kubernetes",
        "description": "Kubernetes orchestration, pods, deployments, services",
        "keywords": "k8s,pod,deployment,service,namespace,helm"
    },
    {
        "name": "Docker",
        "category": "kubernetes",
        "description": "Docker containers, images, Dockerfile",
        "keywords": "docker,container,dockerfile,image"
    },
    {
        "name": "OpenShift",
        "category": "kubernetes",
        "description": "RedHat OpenShift container platform",
        "keywords": "openshift,ocp,routes,projects"
    },
    {
        "name": "Helm",
        "category": "kubernetes",
        "description": "Helm charts, package management for Kubernetes",
        "keywords": "helm,charts,values,release"
    },

    # Cloud Platforms
    {
        "name": "AWS",
        "category": "cloud",
        "description": "Amazon Web Services - EC2, S3, RDS, Lambda",
        "keywords": "aws,ec2,s3,rds,lambda,cloudformation"
    },
    {
        "name": "Azure",
        "category": "cloud",
        "description": "Microsoft Azure cloud platform",
        "keywords": "azure,vm,blob,aks,arm"
    },
    {
        "name": "GCP",
        "category": "cloud",
        "description": "Google Cloud Platform",
        "keywords": "gcp,gce,gke,cloud storage"
    },

    # CI/CD
    {
        "name": "GitLab CI/CD",
        "category": "cicd",
        "description": "GitLab pipelines, runners, CI/CD",
        "keywords": "gitlab,pipeline,runner,ci,cd,yaml"
    },
    {
        "name": "Jenkins",
        "category": "cicd",
        "description": "Jenkins automation server, pipelines",
        "keywords": "jenkins,pipeline,job,build"
    },
    {
        "name": "GitHub Actions",
        "category": "cicd",
        "description": "GitHub Actions workflows and automation",
        "keywords": "github,actions,workflow,yaml"
    },
    {
        "name": "ArgoCD",
        "category": "cicd",
        "description": "GitOps continuous delivery for Kubernetes",
        "keywords": "argocd,gitops,sync,application"
    },

    # Databases
    {
        "name": "PostgreSQL",
        "category": "database",
        "description": "PostgreSQL database administration",
        "keywords": "postgres,postgresql,psql,pg"
    },
    {
        "name": "MySQL",
        "category": "database",
        "description": "MySQL/MariaDB database administration",
        "keywords": "mysql,mariadb,sql"
    },
    {
        "name": "MongoDB",
        "category": "database",
        "description": "MongoDB NoSQL database",
        "keywords": "mongodb,mongo,nosql,document"
    },
    {
        "name": "Redis",
        "category": "database",
        "description": "Redis in-memory data store and cache",
        "keywords": "redis,cache,key-value"
    },

    # Messaging & Queues
    {
        "name": "RabbitMQ",
        "category": "messaging",
        "description": "RabbitMQ message broker",
        "keywords": "rabbitmq,amqp,queue,exchange"
    },
    {
        "name": "Kafka",
        "category": "messaging",
        "description": "Apache Kafka streaming platform",
        "keywords": "kafka,stream,topic,broker"
    },

    # Storage
    {
        "name": "PVC/Storage",
        "category": "storage",
        "description": "Persistent Volume Claims, storage management",
        "keywords": "pvc,pv,storage,volume,nfs,ceph"
    },
    {
        "name": "S3/Object Storage",
        "category": "storage",
        "description": "S3 and object storage solutions",
        "keywords": "s3,object,storage,blob,minio"
    },

    # Monitoring & Observability
    {
        "name": "Prometheus",
        "category": "monitoring",
        "description": "Prometheus monitoring and alerting",
        "keywords": "prometheus,metrics,alert,promql"
    },
    {
        "name": "Grafana",
        "category": "monitoring",
        "description": "Grafana dashboards and visualization",
        "keywords": "grafana,dashboard,visualization"
    },
    {
        "name": "ELK Stack",
        "category": "monitoring",
        "description": "Elasticsearch, Logstash, Kibana",
        "keywords": "elk,elasticsearch,logstash,kibana,logs"
    },

    # Networking
    {
        "name": "Networking",
        "category": "network",
        "description": "Network troubleshooting, DNS, load balancing",
        "keywords": "network,dns,lb,firewall,ingress"
    },
    {
        "name": "Nginx",
        "category": "network",
        "description": "Nginx web server and reverse proxy",
        "keywords": "nginx,proxy,load balancer,ingress"
    },

    # Security
    {
        "name": "Security",
        "category": "security",
        "description": "Security, SSL/TLS, authentication, authorization",
        "keywords": "security,ssl,tls,auth,rbac,secrets"
    },

    # Infrastructure as Code
    {
        "name": "Terraform",
        "category": "iac",
        "description": "Terraform infrastructure as code",
        "keywords": "terraform,tf,iac,hcl"
    },
    {
        "name": "Ansible",
        "category": "iac",
        "description": "Ansible automation and configuration management",
        "keywords": "ansible,playbook,automation"
    },

    # Version Control
    {
        "name": "Git",
        "category": "tools",
        "description": "Git version control, branching, merging",
        "keywords": "git,branch,merge,commit,pull request"
    },

    # Scripting
    {
        "name": "Python",
        "category": "programming",
        "description": "Python scripting and automation",
        "keywords": "python,script,automation"
    },
    {
        "name": "Bash/Shell",
        "category": "programming",
        "description": "Bash and shell scripting",
        "keywords": "bash,shell,script,linux"
    },
]


def populate_skills():
    """Populate predefined skills into database"""

    logger.info("=" * 80)
    logger.info("🎯 Populating Predefined Skills")
    logger.info("=" * 80)

    # Create database session
    engine = create_engine(settings.DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        created_count = 0
        updated_count = 0

        for skill_data in PREDEFINED_SKILLS:
            # Check if skill already exists
            existing = db.query(Skill).filter(
                Skill.name == skill_data["name"]
            ).first()

            if existing:
                # Update existing skill
                existing.category = skill_data["category"]
                existing.description = skill_data["description"]
                existing.keywords = skill_data["keywords"]
                existing.active = True
                updated_count += 1
                logger.debug(f"✏️  Updated: {skill_data['name']}")
            else:
                # Create new skill
                skill = Skill(
                    name=skill_data["name"],
                    category=skill_data["category"],
                    description=skill_data["description"],
                    keywords=skill_data["keywords"],
                    active=True
                )
                db.add(skill)
                created_count += 1
                logger.debug(f"✅ Created: {skill_data['name']}")

        db.commit()

        # Summary
        logger.info("=" * 80)
        logger.info("✅ SKILLS POPULATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"📊 Created: {created_count} new skills")
        logger.info(f"📊 Updated: {updated_count} existing skills")
        logger.info(f"📊 Total: {len(PREDEFINED_SKILLS)} skills available")
        logger.info("=" * 80)

        # Show skills by category
        logger.info("\n📋 Skills by Category:")
        categories = {}
        for skill_data in PREDEFINED_SKILLS:
            cat = skill_data["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(skill_data["name"])

        for category, skill_names in sorted(categories.items()):
            logger.info(f"\n{category.upper()}:")
            for name in skill_names:
                logger.info(f"  - {name}")

        return True

    except Exception as e:
        logger.error(f"❌ Failed to populate skills: {e}")
        db.rollback()
        return False

    finally:
        db.close()


if __name__ == "__main__":
    success = populate_skills()
    sys.exit(0 if success else 1)
