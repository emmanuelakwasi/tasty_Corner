# Deployment Guide

This guide explains how to deploy the Louisiana Restaurant Website to Render (recommended) or other platforms.

## Deployment to Render (Recommended)

### Prerequisites
- GitHub account with the repository pushed
- Render account (sign up at https://render.com - it's free)

### Steps

1. **Sign up/Login to Render**
   - Go to https://render.com
   - Sign up or log in with your GitHub account

2. **Create a New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub account if not already connected
   - Select the repository: `emmanuelakwasi/tasty_Corner`

3. **Configure the Service**
   - **Name**: tasty-corner (or any name you prefer)
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Region**: Choose the closest to your users

4. **Set Environment Variables**
   - Go to "Environment" tab
   - Add a new variable:
     - **Key**: `SECRET_KEY`
     - **Value**: Generate a random secret key (you can use: `python -c "import secrets; print(secrets.token_hex(32))"`)

5. **Create Persistent Disk (Optional but Recommended)**
   - Go to "Disks" tab
   - Click "Create Disk"
   - **Name**: data-disk
   - **Size**: 1 GB
   - **Mount Path**: `/opt/render/project/src/data`
   - This ensures your data persists between deployments

6. **Deploy**
   - Click "Create Web Service"
   - Render will automatically deploy your application
   - Wait for the build to complete (usually 2-5 minutes)
   - Your app will be live at: `https://your-app-name.onrender.com`

### Custom Domain (Optional)
- Go to your service settings
- Click "Custom Domains"
- Add your domain and follow the DNS configuration instructions

## Alternative: Railway Deployment

1. Sign up at https://railway.app
2. Create a new project from GitHub
3. Select your repository
4. Railway will auto-detect Python and deploy
5. Add environment variable `SECRET_KEY` in the Variables tab

## Alternative: Heroku Deployment

1. Install Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli
2. Login: `heroku login`
3. Create app: `heroku create your-app-name`
4. Set secret key: `heroku config:set SECRET_KEY=your-secret-key`
5. Deploy: `git push heroku main`

## Post-Deployment

### Important Notes:
- Your database and CSV files will persist on Render's disk (if configured)
- The app will restart automatically when you push changes to GitHub
- Free tier apps on Render sleep after 15 minutes of inactivity
- For production, consider upgrading to a paid plan for always-on service

### Security:
- ✅ Secret key is now using environment variables
- ⚠️ Update your `SECRET_KEY` in production!
- ⚠️ Consider adding additional security headers

## Troubleshooting

**Build fails?**
- Check the build logs in Render dashboard
- Ensure all dependencies are in `requirements.txt`

**App crashes on startup?**
- Check the logs in Render dashboard
- Verify environment variables are set correctly

**Data not persisting?**
- Ensure you've created a persistent disk and mounted it to `/opt/render/project/src/data`

