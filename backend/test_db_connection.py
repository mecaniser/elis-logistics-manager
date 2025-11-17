"""
Test database connection script
Useful for verifying database connectivity in Railway or locally
"""
import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def test_connection():
    """Test database connection and display connection info"""
    print("🔍 Testing Database Connection...")
    print("-" * 50)
    
    # Get database URL
    database_url = os.getenv("DATABASE_URL", "sqlite:///./elisogistics.db")
    
    # Handle Railway PostgreSQL URL format
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    # Display connection info (mask password)
    display_url = database_url
    if "@" in display_url:
        # Mask password in display
        parts = display_url.split("@")
        if "://" in parts[0]:
            protocol_user = parts[0].split("://")
            if ":" in protocol_user[1]:
                user_pass = protocol_user[1].split(":")
                display_url = f"{protocol_user[0]}://{user_pass[0]}:****@{parts[1]}"
    
    print(f"Database URL: {display_url}")
    print(f"Database Type: {'PostgreSQL' if 'postgresql' in database_url.lower() else 'SQLite'}")
    print("-" * 50)
    
    try:
        # Create engine
        if database_url.startswith("sqlite"):
            engine = create_engine(
                database_url,
                connect_args={"check_same_thread": False}
            )
        else:
            engine = create_engine(database_url)
        
        # Test connection
        print("⏳ Connecting to database...")
        with engine.connect() as conn:
            # Test query
            if database_url.startswith("sqlite"):
                result = conn.execute(text("SELECT 1"))
            else:
                result = conn.execute(text("SELECT 1"))
            
            result.fetchone()
            print("✅ Connection successful!")
            
            # Get database version/info
            if database_url.startswith("postgresql"):
                version_result = conn.execute(text("SELECT version()"))
                version = version_result.fetchone()[0]
                print(f"📊 PostgreSQL Version: {version.split(',')[0]}")
                
                # List tables
                tables_result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """))
                tables = [row[0] for row in tables_result.fetchall()]
                print(f"📋 Tables found: {len(tables)}")
                if tables:
                    print(f"   {', '.join(tables)}")
                else:
                    print("   (No tables found - tables will be created on first app startup)")
            else:
                # SQLite - list tables
                tables_result = conn.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                    ORDER BY name
                """))
                tables = [row[0] for row in tables_result.fetchall()]
                print(f"📋 Tables found: {len(tables)}")
                if tables:
                    print(f"   {', '.join(tables)}")
                else:
                    print("   (No tables found - tables will be created on first app startup)")
        
        print("-" * 50)
        print("✅ Database connection test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Connection failed!")
        print(f"Error: {str(e)}")
        print("-" * 50)
        print("💡 Troubleshooting:")
        print("   1. Check DATABASE_URL environment variable")
        print("   2. Verify database service is running (Railway)")
        print("   3. Check network connectivity")
        print("   4. Verify credentials are correct")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

