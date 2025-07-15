#!/usr/bin/env python3
"""
Setup Neo4j database with proper credentials
"""

import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def setup_neo4j() -> bool:
    """Setup Neo4j with proper credentials."""

    print("🔧 Setting up Neo4j Database")
    print("=" * 50)

    try:
        import neo4j

        print("✅ Neo4j driver is installed")
        print(f"   Version: {neo4j.__version__}")
        print()
    except ImportError:
        print("❌ Neo4j driver is not installed")
        print("   Install with: pip install neo4j")
        return False

    # Try to connect and change password
    print("🔑 Attempting to change default password...")

    try:
        # Connect with default credentials
        driver = neo4j.GraphDatabase.driver(
            "bolt://localhost:7687", auth=("neo4j", "neo4j")
        )

        # Change password
        with driver.session() as session:
            session.run("ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO 'password'")
            print("✅ Password changed successfully!")

        driver.close()

        # Test new connection
        print("🔍 Testing new connection...")
        driver = neo4j.GraphDatabase.driver(
            "bolt://localhost:7687", auth=("neo4j", "password")
        )

        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            if record and record["test"] == 1:
                print("✅ Connection with new password successful!")

                # Get database info
                result = session.run(
                    "CALL dbms.components() YIELD name, versions, edition"
                )
                info = result.single()
                if info:
                    print(
                        f"   Database: {info['name']} {info['versions'][0]} ({info['edition']})"
                    )

                driver.close()
                return True

    except Exception as e:
        print(f"❌ Setup failed: {e}")

        # If it's a credentials expired error, try to handle it
        if "credentials expired" in str(e).lower():
            print()
            print("💡 Manual password change required:")
            print("   1. Open Neo4j Browser at http://localhost:7474")
            print("   2. Login with username: neo4j, password: neo4j")
            print("   3. Change password to 'password' when prompted")
            print("   4. Run this script again")

        return False

    return False


if __name__ == "__main__":
    success = setup_neo4j()
    if success:
        print("\n🎉 Neo4j setup completed successfully!")
        print("   You can now run the enhanced Neo4j tests.")
    else:
        print("\n❌ Neo4j setup failed.")
        print("   Please follow the manual setup instructions above.")
