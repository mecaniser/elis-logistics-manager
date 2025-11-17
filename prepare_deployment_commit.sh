#!/bin/bash
# Script to prepare files for Railway deployment commit

echo "🚀 Preparing files for Railway deployment commit..."
echo ""

# Stage deployment documentation
echo "📚 Staging deployment documentation..."
git add DATABASE_CONNECTION.md
git add DEPLOYMENT_SUMMARY.md
git add RAILWAY_DEPLOYMENT.md
git add RAILWAY_QUICK_START.md
git add COMMIT_BEFORE_DEPLOYMENT.md

# Stage Railway configuration
echo "⚙️  Staging Railway configuration..."
git add railway.json
git add Procfile
git add .gitignore

# Stage database test script
echo "🔍 Staging database test script..."
git add backend/test_db_connection.py

# Stage application code changes
echo "💻 Staging application code changes..."
git add backend/app/main.py
git add backend/app/models/repair.py
git add backend/app/routers/analytics.py
git add backend/app/routers/repairs.py
git add backend/app/routers/settlements.py
git add backend/app/schemas/repair.py
git add backend/app/schemas/settlement.py

# Stage migration scripts
echo "🔄 Staging migration scripts..."
git add backend/migrate_add_expense_categories.py
git add backend/migrate_add_image_paths.py
git add backend/migrate_add_vin.py

# Stage frontend changes
echo "🎨 Staging frontend changes..."
git add frontend/src/pages/Dashboard.tsx
git add frontend/src/pages/Extractor.tsx
git add frontend/src/pages/Repairs.tsx
git add frontend/src/pages/Settlements.tsx
git add frontend/src/services/api.ts

# Stage README
echo "📖 Staging README..."
git add README.md

echo ""
echo "✅ Files staged for commit!"
echo ""
echo "📋 Review what will be committed:"
git status --short
echo ""
echo "💡 To commit, run:"
echo "   git commit -m 'Add Railway deployment configuration and update application'"
echo ""
echo "⚠️  Note: Utility scripts and data files are NOT staged."
echo "   Review COMMIT_BEFORE_DEPLOYMENT.md for details."

