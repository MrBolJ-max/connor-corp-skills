"""
Stripe Checkout API for AI Sales Caller
Simple Express.js backend for Stripe payments

Usage:
    node stripe-checkout.js
"""

const express = require('express');
const stripe = require('stripe')(process.env.STRIPE_SECRET_KEY);
const cors = require('cors');
const app = express();

app.use(cors());
app.use(express.json());

// Product prices (in cents)
const PRICES = {
    starter: 49700,    // $497
    pro: 99700,        // $997
    enterprise: 249700, // $2,497
};

app.post('/api/create-checkout-session', async (req, res) => {
    try {
        const { tier = 'starter', customer_email } = req.body;
        const amount = PRICES[tier] || PRICES.starter;

        const session = await stripe.checkout.sessions.create({
            payment_method_types: ['card'],
            line_items: [{
                price_data: {
                    currency: 'usd',
                    product_data: {
                        name: `AI Sales Caller — ${tier.charAt(0).toUpperCase() + tier.slice(1)}`,
                        description: 'AI-powered sales calling system with lead research, voice calling, objection handling, and meeting booking.',
                    },
                    unit_amount: amount,
                },
                quantity: 1,
            }],
            mode: 'payment',
            success_url: `${req.headers.origin || 'https://mrbolj-max.github.io/connor-corp-skills'}/success.html`,
            cancel_url: `${req.headers.origin || 'https://mrbolj-max.github.io/connor-corp-skills'}/cancel.html`,
            customer_email: customer_email,
            metadata: {
                tier: tier,
                product: 'ai-sales-caller',
            },
        });

        res.json({ id: session.id, url: session.url });
    } catch (error) {
        console.error('Stripe error:', error);
        res.status(500).json({ error: error.message });
    }
});

app.post('/api/webhook', express.raw({ type: 'application/json' }), async (req, res) => {
    const sig = req.headers['stripe-signature'];
    const endpointSecret = process.env.STRIPE_WEBHOOK_SECRET;

    let event;
    try {
        event = stripe.webhooks.constructEvent(req.body, sig, endpointSecret);
    } catch (err) {
        console.error('Webhook error:', err);
        return res.status(400).send(`Webhook Error: ${err.message}`);
    }

    if (event.type === 'checkout.session.completed') {
        const session = event.data.object;
        console.log('✅ Payment successful:', session.id);
        console.log('Customer:', session.customer_email);
        console.log('Tier:', session.metadata.tier);
        
        // TODO: Send download email, add to customer list
    }

    res.json({ received: true });
});

app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', time: new Date().toISOString() });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`🚀 Stripe checkout server running on port ${PORT}`);
    console.log(`📦 Product: AI Sales Caller`);
    console.log(`💰 Tiers: Starter $497 | Pro $997 | Enterprise $2,497`);
});

module.exports = app;
