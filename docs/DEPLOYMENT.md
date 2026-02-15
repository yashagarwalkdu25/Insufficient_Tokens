# Deployment Guide

## Local Docker

```bash
# Create .env file
cp .env.example .env
# Edit .env with your API keys

# Start services
docker-compose up -d
```

**Access**: http://localhost:8501 (UI) | http://localhost:5001 (API)

## AWS EC2 Deployment (Docker Hub)

### 1. Build and Push Image Locally

```bash
# Build image for linux/amd64 (EC2 architecture)
docker buildx build --platform linux/amd64 -t your-dockerhub-username/claim-verifier:latest . --push

# Or if buildx not available:
docker build --platform linux/amd64 -t your-dockerhub-username/claim-verifier:latest .
docker login
docker push your-dockerhub-username/claim-verifier:latest
```

### 2. Setup EC2

**For Amazon Linux 2023:**

```bash
# SSH into EC2
ssh -i your-key.pem ec2-user@your-ec2-ip

# Update system
sudo yum update -y

# Install Docker
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Logout and login again for group changes
exit
```

**For Amazon Linux 2:**

```bash
# SSH into EC2
ssh -i your-key.pem ec2-user@your-ec2-ip

# Update and install Docker
sudo yum update -y
sudo amazon-linux-extras install docker -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

# Logout and login again
exit
```

### 3. Deploy Container

```bash
# SSH into EC2
ssh -i your-key.pem ec2-user@your-ec2-ip

# Pull image
docker pull your-dockerhub-username/claim-verifier:latest

# Create data directory
mkdir -p ~/chroma_db

# Run container
docker run -d \
  -p 8501:8501 -p 5001:5001 \
  -e OPENAI_API_KEY=sk-your-key-here \
  -e TAVILY_API_KEY=tvly-your-key-here \
  -v ~/chroma_db:/app/chroma_db \
  --restart unless-stopped \
  --name claim-verifier \
  your-dockerhub-username/claim-verifier:latest
```

### 4. Configure Security Group

Add inbound rules in AWS Console:
- **Port 8501** (TCP) - Streamlit UI - Source: 0.0.0.0/0
- **Port 5001** (TCP) - Flask API - Source: 0.0.0.0/0
- **Port 22** (TCP) - SSH - Source: Your IP

**Access**: http://your-ec2-ip:8501

## Management Commands

```bash
# View logs
docker logs -f claim-verifier

# Restart
docker restart claim-verifier

# Stop
docker stop claim-verifier

# Update (pull new image and recreate)
docker pull your-dockerhub-username/claim-verifier:latest
docker stop claim-verifier && docker rm claim-verifier
# Then run docker run command again

# Reset database
rm -rf ~/chroma_db/* && docker restart claim-verifier
```
