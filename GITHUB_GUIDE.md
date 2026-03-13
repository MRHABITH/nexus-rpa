# 📡 GitHub Setup Guide — Nexus RPA

Follow these steps to push your project to GitHub and enable Vercel auto-deployments.

---

## 📸 Step 1: Create a Repository on GitHub
1.  Go to [github.com/new](https://github.com/new).
2.  Name it `nexus-rpa` (or any name you like).
3.  Keep it **Public** or **Private**.
4.  **Do NOT** initialize with a README, license, or gitignore (we already have them!).
5.  Click **Create repository**.

---

## 💻 Step 2: Push your local code
Open your terminal in `c:\Users\habit\Downloads\simple` and run:

```bash
# 1. Initialize git (if not already done)
git init

# 2. Add all files
git add .

# 3. Commit
git commit -m "feat: initial cloud-ready release with Vercel config"

# 4. Rename branch to main
git branch -M main

# 5. Link to your GitHub Repo
# REPLACE <your-username> and <repo-name> with your values!
git remote add origin https://github.com/<your-username>/<repo-name>.git

# 6. Push!
git push -u origin main
```

---

## 🔗 Step 3: Connect to Vercel
1.  Go to the [Vercel Dashboard](https://vercel.com/new).
2.  Find your `nexus-rpa` repository and click **Import**.
3.  Add your **Environment Variables** (see `DEPLOYMENT_GUIDE.md`):
    - `SUPABASE_URL`
    - `SUPABASE_KEY`
    - `GROQ_API_KEY`
4.  Click **Deploy**.

---

✅ Every time you `git push` in the future, Vercel will automatically update your live site!
