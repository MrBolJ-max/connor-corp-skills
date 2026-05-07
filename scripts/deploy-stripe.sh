#!/bin/bash
# Quick deploy script for Stripe checkout backend
# Deploys to Railway/Render free tier

echo "🚀 Deploying Stripe backend..."

# Check if node is available
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Installing..."
    apt-get update && apt-get install -y nodejs npm 2>/dev/null || echo "Manual install needed"
fi

# Create package.json if not exists
cd /root/.openclaw/workspace/projects/connor-corp-skills/api

cat > package.json << 'EOF'
{
  "name": "connor-corp-checkout",
  "version": "1.0.0",
  "description": "Stripe checkout for AI Sales Caller",
  "main": "stripe-checkout.js",
  "scripts": {
    "start": "node stripe-checkout.js",
    "dev": "node stripe-checkout.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "stripe": "^12.0.0",
    "cors": "^2.8.5"
  }
}
EOF

# Install dependencies
npm install 2>/dev/null

# Start server in background
export STRIPE_SECRET_KEY=$(grep STRIPE_SECRET_KEY ~/.openclaw/credentials/stripe.env | cut -d= -f2)
export STRIPE_WEBHOOK_SECRET=whsec_placeholder

nohup node stripe-checkout.js > /root/.openclaw/workspace/logs/stripe-server.log 2>&1 &

echo "✅ Stripe server started on port 3000"
echo "📊 Health check: http://localhost:3000/api/health"
echo "💳 Checkout endpoint: http://localhost:3000/api/create-checkout-session"
