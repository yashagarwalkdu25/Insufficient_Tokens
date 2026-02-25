# Deployment Guide

## Local Docker

```bash
cp .env.example .env
# Edit .env with your API keys

docker compose up -d
```

**Access**: http://localhost:8501

## AWS EC2 Deployment (Docker Hub)

### 1. Build and Push Image Locally

```bash
# Build image for linux/amd64 (EC2 architecture)
docker buildx build --platform linux/amd64 -t your-dockerhub-username/tripsaathi:latest . --push

# Or if buildx not available:
docker build --platform linux/amd64 -t your-dockerhub-username/tripsaathi:latest .
docker login
docker push your-dockerhub-username/tripsaathi:latest
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
docker pull your-dockerhub-username/tripsaathi:latest

# Create db directory
mkdir -p ~/tripsaathi/db

# Run container
docker run -d \
  -p 8501:8501 \
  -e OPENAI_API_KEY=sk-your-key-here \
  -e AMADEUS_CLIENT_ID=your-amadeus-client-id \
  -e AMADEUS_CLIENT_SECRET=your-amadeus-client-secret \
  -e LITEAPI_KEY=your-liteapi-key \
  -e GOOGLE_PLACES_KEY=your-google-places-key \
  -e GOOGLE_DIRECTIONS_KEY=your-google-directions-key \
  -e OPENWEATHERMAP_KEY=your-openweathermap-key \
  -e REDDIT_CLIENT_ID=your-reddit-client-id \
  -e REDDIT_CLIENT_SECRET=your-reddit-client-secret \
  -v ~/tripsaathi/db:/app/db \
  --restart unless-stopped \
  --name tripsaathi \
  your-dockerhub-username/tripsaathi:latest
```

### 4. Configure Security Group

Add inbound rules in AWS Console:
- **Port 8501** (TCP) — Streamlit UI — Source: 0.0.0.0/0
- **Port 22** (TCP) — SSH — Source: Your IP

**Access**: http://your-ec2-ip:8501

## Management Commands

```bash
# View logs
docker logs -f tripsaathi

# Restart
docker restart tripsaathi

# Stop
docker stop tripsaathi

# Update (pull new image and recreate)
docker pull your-dockerhub-username/tripsaathi:latest
docker stop tripsaathi && docker rm tripsaathi
# Then run docker run command again

# Reset DB
rm -rf ~/tripsaathi/db && mkdir -p ~/tripsaathi/db && docker restart tripsaathi

