# AeroChat Shopify App

A Shopify app that integrates with AeroChat to provide chat functionality for Shopify stores.

## Features

- Shopify OAuth integration
- Store management and subscription handling
- Webhook support for app uninstall and subscription events
- Database integration with PostgreSQL
- Third-party API integration with AeroChat

## Prerequisites

- Python 3.8+
- PostgreSQL database
- Shopify Partner account
- AeroChat API access

## Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd new-shopify
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp env.template .env
   ```
   
   Edit `.env` file with your actual values:
   - `SHOPIFY_API_KEY`: Your Shopify app's API key
   - `SHOPIFY_API_SECRET`: Your Shopify app's API secret
   - `SHOPIFY_REDIRECT_URI`: Your app's callback URL
   - `DATABASE_URL`: Your PostgreSQL database connection string
   - `THIRD_PARTY_BASE`: Your AeroChat API base URL
   - `SECRET_KEY`: A random secret key for Flask sessions

5. **Set up the database**
   - Create a PostgreSQL database
   - Update the `DATABASE_URL` in your `.env` file
   - The app will automatically create the required tables on first run

6. **Run the application**
   ```bash
   python main.py
   ```

   The app will start on `http://localhost:5000`

## Shopify App Configuration

1. **Create a Shopify Partner account** at https://partners.shopify.com
2. **Create a new app** in your Partner dashboard
3. **Configure the app settings**:
   - App URL: `https://your-domain.com`
   - Allowed redirection URLs: `https://your-domain.com/oauth/callback`
   - Webhook endpoints:
     - App uninstalled: `https://your-domain.com/webhooks/uninstall`
     - Subscription updated: `https://your-domain.com/webhooks/subscription`

## Deployment on Render

### Prerequisites
- GitHub repository with your code
- Render account
- PostgreSQL database (can be created on Render)

### Steps

1. **Connect your GitHub repository to Render**
   - Go to https://render.com
   - Sign up/Login with your GitHub account
   - Click "New +" → "Web Service"
   - Connect your GitHub repository

2. **Configure the web service**
   - **Name**: Choose a name for your service
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python main.py`
   - **Instance Type**: Choose based on your needs (Free tier available)

3. **Set up environment variables**
   In the Render dashboard, go to your service → Environment tab and add:
   ```
   SHOPIFY_API_KEY=your_shopify_api_key
   SHOPIFY_API_SECRET=your_shopify_api_secret
   SHOPIFY_SCOPES=read_products,write_products,read_orders,write_orders
   SHOPIFY_REDIRECT_URI=https://your-render-app.onrender.com/oauth/callback
   SHOPIFY_APP_HANDLE=your-app-handle
   THIRD_PARTY_BASE=https://your-aerochat-api.com
   DATABASE_URL=postgresql://username:password@host:port/database
   SECRET_KEY=your-random-secret-key
   ```

4. **Set up PostgreSQL database**
   - In Render dashboard, click "New +" → "PostgreSQL"
   - Choose a name and plan
   - Copy the connection string and use it as `DATABASE_URL`

5. **Update Shopify app settings**
   - Update your Shopify app's URLs to use your Render domain
   - Update webhook URLs to point to your Render app

6. **Deploy**
   - Click "Create Web Service"
   - Render will automatically build and deploy your app

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SHOPIFY_API_KEY` | Your Shopify app's API key | Yes |
| `SHOPIFY_API_SECRET` | Your Shopify app's API secret | Yes |
| `SHOPIFY_SCOPES` | Shopify API scopes | Yes |
| `SHOPIFY_REDIRECT_URI` | OAuth callback URL | Yes |
| `SHOPIFY_APP_HANDLE` | Your app handle | Yes |
| `THIRD_PARTY_BASE` | AeroChat API base URL | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SECRET_KEY` | Flask secret key | Yes |

## Project Structure

```
├── main.py                 # Flask application entry point
├── config.py               # Configuration and environment variables
├── database.py             # Database models and connection
├── routes.py               # Main application routes
├── webhook_routes.py       # Webhook handlers
├── webhooks.py             # Webhook registration
├── utils.py                # Utility functions
├── requirements.txt        # Python dependencies
├── shopify.app.toml        # Shopify app configuration
├── templates/              # HTML templates
├── extensions/             # Shopify app extensions
└── env.template            # Environment variables template
```

## API Endpoints

- `GET /` - Home page
- `GET /install` - Shopify app installation
- `GET /oauth/callback` - OAuth callback handler
- `GET /check_subscription` - Check subscription status
- `POST /webhooks/uninstall` - App uninstall webhook
- `POST /webhooks/subscription` - Subscription webhook

## Troubleshooting

### Common Issues

1. **Database connection errors**
   - Verify your `DATABASE_URL` is correct
   - Ensure your database is accessible from your deployment environment

2. **Shopify OAuth errors**
   - Check that your redirect URI matches exactly in Shopify Partner dashboard
   - Verify your API key and secret are correct

3. **Webhook not receiving data**
   - Ensure webhook URLs are publicly accessible
   - Check that your app has the necessary permissions

### Logs

Application logs are written to `shopify_app.log` and also displayed in the console.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License.
