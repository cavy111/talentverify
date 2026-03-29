# Talent Verify Deployment Guide

This guide explains how to deploy the Talent Verify platform on a budget VPS ($6/month) using Docker and Docker Compose.

## Prerequisites

- A VPS running Ubuntu 22.04 (or similar)
- Domain name pointed to your VPS IP
- Basic command line knowledge
- SSH access to your VPS

## VPS Providers (Budget Options)

### Hetzner ($6/month)
- **Plan**: CX11 (Cloud Server)
- **Specs**: 2 vCPU, 4 GB RAM, 20 GB SSD
- **Pros**: Excellent performance, German privacy laws
- **Signup**: https://www.hetzner.com/cloud

### DigitalOcean ($6/month)
- **Plan**: Basic Droplet (Regular Performance)
- **Specs**: 1 vCPU, 1 GB RAM, 25 GB SSD (may need upgrade)
- **Pros**: Easy to use, good documentation
- **Signup**: https://www.digitalocean.com/

### Vultr ($6/month)
- **Plan**: Regular Performance
- **Specs**: 1 vCPU, 1 GB RAM, 25 GB SSD
- **Pros**: Global locations, competitive pricing
- **Signup**: https://www.vultr.com/

**Recommendation**: Hetzner CX11 offers the best value for this application.

## Initial VPS Setup

### 1. Connect to Your VPS
```bash
ssh root@your-vps-ip
```

### 2. Update System
```bash
apt update && apt upgrade -y
```

### 3. Install Docker and Docker Compose
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh

# Add user to docker group
usermod -aG docker root

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Create docker group (if not exists)
groupadd docker
```

### 4. Install Additional Tools
```bash
apt install -y git curl wget htop ufw
```

### 5. Configure Firewall
```bash
# Allow SSH, HTTP, HTTPS
ufw allow ssh
ufw allow 80
ufw allow 443

# Enable firewall
ufw --force enable
```

### 6. Create Application Directory
```bash
mkdir -p /opt/talentverify
cd /opt/talentverify
```

## Domain Setup

### 1. Point Domain to VPS
In your domain registrar's DNS settings:
```
A Record: @ -> YOUR_VPS_IP
A Record: www -> YOUR_VPS_IP
```

### 2. Wait for DNS Propagation
```bash
# Check if DNS is pointing correctly
nslookup your-domain.com
```

## Application Deployment

### 1. Clone the Repository
```bash
cd /opt/talentverify
git clone https://github.com/your-username/talentverify.git .
```

### 2. Set Environment Variables
Create `.env` file:
```bash
nano .env
```

Add the following configuration:
```bash
# Generate secure keys
SECRET_KEY=$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')
FIELD_ENCRYPTION_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')
SEARCH_HMAC_KEY=$(python -c 'import secrets, hashlib; print(hashlib.sha256(secrets.token_bytes(32)).hexdigest())')

# Database configuration
DB_PASSWORD=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-25)

# Application settings
DEBUG=False
DB_NAME=talentverify
DB_USER=postgres
DB_HOST=db
DB_PORT=5432
REDIS_URL=redis://redis:6379/0

# Admin user
TV_ADMIN_EMAIL=admin@your-domain.com
TV_ADMIN_PASSWORD=$(openssl rand -base64 16 | tr -d "=+/" | cut -c1-12)

# Frontend
VITE_API_URL=https://your-domain.com/api
```

### 3. Create Docker Compose Override
Create `docker-compose.override.yml`:
```bash
nano docker-compose.override.yml
```

```yaml
version: '3.8'

services:
  nginx:
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/ssl:/etc/nginx/ssl:ro

  web:
    environment:
      - VITE_API_URL=https://your-domain.com/api
```

### 4. Start the Application
```bash
# Start all services
docker-compose up -d

# Wait for services to initialize
sleep 30

# Run database migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py create_default_roles

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput
```

### 5. Verify Deployment
```bash
# Check service status
docker-compose ps

# Check logs
docker-compose logs -f web

# Test health endpoint
curl http://localhost/health
```

## SSL Certificate Setup (HTTPS)

### 1. Install Certbot
```bash
apt install -y certbot python3-certbot-nginx
```

### 2. Obtain SSL Certificate
```bash
certbot --nginx -d your-domain.com -d www.your-domain.com
```

### 3. Update Nginx Configuration
Edit `nginx/default.conf` and uncomment the HTTPS sections:
```bash
nano nginx/default.conf
```

Replace `your-domain.com` with your actual domain in the HTTPS server block.

### 4. Test SSL Configuration
```bash
# Test nginx configuration
nginx -t

# Reload nginx
docker-compose restart nginx

# Test SSL certificate
https://www.ssllabs.com/ssltest/
```

### 5. Set Up Auto-Renewal
```bash
# Add cron job for auto-renewal
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet && docker-compose restart nginx") | crontab -
```

## Monitoring and Maintenance

### 1. Basic Monitoring Script
Create `/opt/talentverify/monitor.sh`:
```bash
#!/bin/bash

echo "=== Talent Verify Status ==="
echo "Date: $(date)"
echo ""

# Check Docker services
echo "Docker Services:"
docker-compose ps
echo ""

# Check disk space
echo "Disk Usage:"
df -h /
echo ""

# Check memory usage
echo "Memory Usage:"
free -h
echo ""

# Check application health
echo "Application Health:"
curl -s http://localhost/health || echo "Health check failed"
echo ""

# Check SSL certificate
echo "SSL Certificate:"
openssl s_client -connect your-domain.com:443 -servername your-domain.com 2>/dev/null | openssl x509 -noout -dates | grep notAfter
echo ""
```

Make it executable:
```bash
chmod +x monitor.sh
```

### 2. Log Rotation
Create `/etc/logrotate.d/talentverify`:
```
/opt/talentverify/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker-compose restart web
    endscript
}
```

### 3. Backup Script
Create `/opt/talentverify/backup.sh`:
```bash
#!/bin/bash

BACKUP_DIR="/opt/talentverify/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# Database backup
docker-compose exec -T db pg_dump -U postgres talentverify > $BACKUP_DIR/db_backup_$DATE.sql

# Media files backup
tar -czf $BACKUP_DIR/media_backup_$DATE.tar.gz media/

# Environment file backup
cp .env $BACKUP_DIR/env_backup_$DATE

# Clean old backups (keep last 7 days)
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
find $BACKUP_DIR -name "env_backup_*" -mtime +7 -delete

echo "Backup completed: $DATE"
```

Make it executable and add to cron:
```bash
chmod +x backup.sh
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/talentverify/backup.sh") | crontab -
```

## Performance Optimization

### 1. Database Optimization
```bash
# Connect to database
docker-compose exec db psql -U postgres talentverify

# Add indexes (if not already created)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_employee_name_search_hash ON core_employee(name_search_hash);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_employment_record_employee_company ON core_employmentrecord(employee_id, company_id);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_audit_log_timestamp ON core_auditlog(timestamp);
```

### 2. Redis Configuration
Create `redis.conf`:
```bash
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

Update `docker-compose.yml` redis service:
```yaml
redis:
  image: redis:7-alpine
  volumes:
    - redis_data:/data
    - ./redis.conf:/usr/local/etc/redis/redis.conf
  command: redis-server /usr/local/etc/redis/redis.conf
```

### 3. Nginx Caching
Add to `nginx/default.conf`:
```nginx
# Add to http block
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=api_cache:10m max_size=100m inactive=60m;

# Add to server block for API
location /api/search/ {
    proxy_cache api_cache;
    proxy_cache_valid 200 5m;
    proxy_cache_key "$scheme$request_method$host$request_uri";
    proxy_pass http://django;
    # ... other proxy settings
}
```

## Security Hardening

### 1. SSH Security
```bash
# Edit SSH config
nano /etc/ssh/sshd_config

# Recommended settings:
# Port 2222  (change from default 22)
# PermitRootLogin no
# PasswordAuthentication no
# PubkeyAuthentication yes
# MaxAuthTries 3

# Restart SSH
systemctl restart ssh
```

### 2. Fail2Ban Setup
```bash
apt install -y fail2ban

# Create jail configuration
cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
logpath = /var/log/nginx/error.log
maxretry = 5
EOF

systemctl enable fail2ban
systemctl start fail2ban
```

### 3. Automatic Updates
```bash
# Install unattended-upgrades
apt install -y unattended-upgrades apt-listchanges

# Configure automatic security updates
dpkg-reconfigure -plow unattended-upgrades
```

## Troubleshooting

### Common Issues

#### 1. Database Connection Errors
```bash
# Check database logs
docker-compose logs db

# Test database connection
docker-compose exec web python manage.py dbshell
```

#### 2. Frontend Not Loading
```bash
# Check nginx logs
docker-compose logs nginx

# Test nginx configuration
docker-compose exec nginx nginx -t

# Restart nginx
docker-compose restart nginx
```

#### 3. High Memory Usage
```bash
# Check memory usage
docker stats

# Restart services if needed
docker-compose restart
```

#### 4. SSL Certificate Issues
```bash
# Check certificate status
certbot certificates

# Force renewal
certbot renew --force-renewal

# Test nginx SSL
openssl s_client -connect your-domain.com:443
```

### Log Locations
- **Application logs**: `docker-compose logs web`
- **Database logs**: `docker-compose logs db`
- **Nginx logs**: `docker-compose logs nginx`
- **System logs**: `/var/log/syslog`

## Scaling Considerations

### When to Upgrade VPS
- CPU usage consistently > 80%
- Memory usage > 80%
- Database query times > 500ms
- Response times > 2 seconds

### Upgrade Path
1. **Hetzner**: CX21 (4 GB RAM) → CX31 (8 GB RAM)
2. **DigitalOcean**: Upgrade to 2 GB RAM → 4 GB RAM
3. **Add separate database server** for large deployments

## Cost Breakdown (Monthly)

### Hetzner CX21 (Recommended)
- **VPS**: $9.99/month
- **Domain**: $12-15/year ($1-1.25/month)
- **Total**: ~$11/month

### DigitalOcean (Alternative)
- **VPS**: $12/month (2 GB RAM needed)
- **Domain**: $12-15/year ($1-1.25/month)
- **Total**: ~$13/month

## Support and Maintenance

### Regular Tasks
- **Weekly**: Check logs and monitor performance
- **Monthly**: Update system packages
- **Quarterly**: Review security updates and backups
- **Annually**: Renew domain and SSL certificates

### Emergency Contacts
- **VPS Provider**: Support ticket system
- **Domain Registrar**: DNS management
- **Application Issues**: Check logs and restart services

## Final Checklist

Before going live, ensure:
- [ ] All environment variables are set
- [ ] SSL certificate is installed and auto-renewing
- [ ] Database migrations are run
- [ ] Superuser account is created
- [ ] Backups are configured
- [ ] Monitoring is working
- [ ] Security settings are applied
- [ ] Domain is pointing correctly
- [ ] Load testing has been performed

Your Talent Verify platform should now be running securely on your budget VPS!
