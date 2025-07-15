#!/usr/bin/env python3
"""
Comprehensive Neo4j test suite for CodeFusion
Consolidates connection, enhanced features, and query testing
"""

import sys
from pathlib import Path

# Add the parent directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from cf.kb.knowledge_base import create_knowledge_base, CodeEntity, CodeRelationship
from datetime import datetime

class TestNeo4jConnection:
    """Test Neo4j connection with different configurations."""
    
    def test_connection_configs(self):
        """Test different Neo4j connection configurations."""
        
        print("🔧 Testing Neo4j Connection Configurations")
        print("=" * 50)
        
        # Test configurations
        configs = [
            {
                "name": "Local Docker (default)",
                "uri": "bolt://localhost:7687",
                "user": "neo4j",
                "password": "password"
            },
            {
                "name": "Local Docker (neo4j/neo4j)",
                "uri": "bolt://localhost:7687",
                "user": "neo4j",
                "password": "neo4j"
            },
            {
                "name": "Neo4j Desktop (default)",
                "uri": "bolt://localhost:7687",
                "user": "neo4j",
                "password": "neo4j"
            },
            {
                "name": "Alternative port",
                "uri": "bolt://localhost:7688",
                "user": "neo4j",
                "password": "password"
            }
        ]
        
        try:
            import neo4j
            print("✅ Neo4j driver is installed")
            print(f"   Version: {neo4j.__version__}")
            print()
        except ImportError:
            print("❌ Neo4j driver is not installed")
            print("   Install with: pip install neo4j")
            return False
        
        for config in configs:
            print(f"🔍 Testing: {config['name']}")
            print(f"   URI: {config['uri']}")
            print(f"   User: {config['user']}")
            
            try:
                driver = neo4j.GraphDatabase.driver(
                    config['uri'],
                    auth=(config['user'], config['password'])
                )
                
                # Test connection
                with driver.session() as session:
                    result = session.run("RETURN 1 as test")
                    record = result.single()
                    if record and record["test"] == 1:
                        print("   ✅ Connection successful!")
                        
                        # Get some basic info
                        result = session.run("CALL dbms.components() YIELD name, versions, edition")
                        info = result.single()
                        if info:
                            print(f"   Database: {info['name']} {info['versions'][0]} ({info['edition']})")
                        
                        driver.close()
                        print()
                        return True
                        
            except Exception as e:
                print(f"   ❌ Connection failed: {e}")
                
            print()
        
        print("❌ All connection attempts failed")
        return False


class TestNeo4jEnhanced:
    """Test enhanced Neo4j features with advanced graph analytics."""
    
    def test_enhanced_features(self):
        """Test enhanced Neo4j features with fallback to in-memory."""
        
        print("🧪 Testing Enhanced Neo4j Knowledge Base Features")
        print("=" * 50)
        
        # Create Neo4j KB (will fallback to in-memory if Neo4j unavailable)
        kb = create_knowledge_base(
            kb_type="neo4j",
            storage_path="./test_kb",
            uri="bolt://localhost:7687",
            user="neo4j", 
            password="password"
        )
        
        print(f"✅ Created knowledge base: {type(kb).__name__}")
        print(f"   Connected to Neo4j: {kb.driver is not None}")
        print()
        
        # Create sample entities
        entities = [
            CodeEntity(
                id="main_py", name="main.py", type="file", path="./main.py",
                content="from fastapi import FastAPI\napp = FastAPI()", 
                language="python", size=100, created_at=datetime.now(), metadata={}
            ),
            CodeEntity(
                id="app_py", name="app.py", type="file", path="./app.py",
                content="from main import app\nfrom models import User", 
                language="python", size=150, created_at=datetime.now(), metadata={}
            ),
            CodeEntity(
                id="models_py", name="models.py", type="file", path="./models.py",
                content="class User:\n    def __init__(self):\n        pass", 
                language="python", size=80, created_at=datetime.now(), metadata={}
            ),
            CodeEntity(
                id="utils_py", name="utils.py", type="file", path="./utils.py",
                content="def helper():\n    return 'help'", 
                language="python", size=50, created_at=datetime.now(), metadata={}
            ),
            CodeEntity(
                id="user_class", name="User", type="class", path="./models.py",
                content="class User:\n    def __init__(self):\n        pass", 
                language="python", size=30, created_at=datetime.now(), metadata={}
            )
        ]
        
        # Add entities to KB
        print("📝 Adding entities to knowledge base...")
        for entity in entities:
            kb.add_entity(entity)
        
        # Create relationships
        relationships = [
            CodeRelationship(
                id="main_imports_fastapi", source_id="main_py", target_id="app_py",
                relationship_type="imports", strength=0.9, metadata={}
            ),
            CodeRelationship(
                id="app_imports_main", source_id="app_py", target_id="main_py",
                relationship_type="imports", strength=0.8, metadata={}
            ),
            CodeRelationship(
                id="app_imports_models", source_id="app_py", target_id="models_py",
                relationship_type="imports", strength=0.7, metadata={}
            ),
            CodeRelationship(
                id="models_contains_user", source_id="models_py", target_id="user_class",
                relationship_type="contains", strength=1.0, metadata={}
            ),
            CodeRelationship(
                id="main_similar_app", source_id="main_py", target_id="app_py",
                relationship_type="similar", strength=0.6, metadata={}
            )
        ]
        
        print("🔗 Adding relationships to knowledge base...")
        for rel in relationships:
            kb.add_relationship(rel)
        
        print(f"✅ Added {len(entities)} entities and {len(relationships)} relationships")
        print()
        
        # Test enhanced features
        print("🔍 Testing Enhanced Graph Features:")
        print("-" * 30)
        
        # 1. Test central entities
        print("1. Finding central entities:")
        central_entities = kb.find_central_entities(limit=3)
        for entity, degree in central_entities:
            print(f"   • {entity.name} (degree: {degree})")
        print()
        
        # 2. Test shortest path
        print("2. Finding shortest path between main.py and User class:")
        path = kb.find_shortest_path("main_py", "user_class")
        if path:
            path_names = [e.name for e in path]
            print(f"   Path: {' → '.join(path_names)}")
        else:
            print("   No path found")
        print()
        
        # 3. Test entity neighborhood
        print("3. Finding neighborhood of app.py:")
        neighbors = kb.get_entity_neighborhood("app_py", depth=2)
        neighbor_names = [e.name for e in neighbors]
        print(f"   Neighbors: {', '.join(neighbor_names)}")
        print()
        
        # 4. Test entity clusters
        print("4. Finding entity clusters:")
        clusters = kb.find_entity_clusters(min_cluster_size=2)
        for i, cluster in enumerate(clusters):
            cluster_names = [e.name for e in cluster]
            print(f"   Cluster {i+1}: {', '.join(cluster_names)}")
        print()
        
        # 5. Test architectural patterns
        print("5. Analyzing architectural patterns:")
        patterns = kb.analyze_architectural_patterns()
        for pattern in patterns:
            print(f"   Pattern: {pattern['pattern_type']}")
            print(f"   Description: {pattern['description']}")
            if 'entities' in pattern:
                for entity_info in pattern['entities'][:3]:  # Show first 3
                    if isinstance(entity_info, dict):
                        print(f"     • {entity_info['entity'].name} ({entity_info.get('connections', 'N/A')} connections)")
                    else:
                        print(f"     • {entity_info.name}")
        print()
        
        # 6. Test similarity search
        print("6. Finding similar entities to main.py:")
        similar = kb.find_similar_entities("main_py", similarity_threshold=0.5)
        for entity, similarity in similar:
            print(f"   • {entity.name} (similarity: {similarity:.2f})")
        print()
        
        # 7. Test statistics
        print("7. Knowledge base statistics:")
        stats = kb.get_statistics()
        print(f"   Total entities: {stats['total_entities']}")
        print(f"   Total relationships: {stats['total_relationships']}")
        print(f"   Neo4j available: {stats.get('neo4j_available', 'N/A')}")
        print(f"   Connected to Neo4j: {stats.get('connected', 'N/A')}")
        print()
        
        print("✅ Enhanced Neo4j testing completed!")
        return True


class TestNeo4jQueries:
    """Test comprehensive Neo4j query functionality."""
    
    def test_query_functionality(self):
        """Test various query scenarios with Neo4j knowledge base."""
        
        print("🔍 Testing Neo4j Query Functionality")
        print("=" * 50)
        
        # Create Neo4j KB
        kb = create_knowledge_base(
            kb_type="neo4j",
            storage_path="./test_kb",
            uri="bolt://localhost:7687",
            user="neo4j", 
            password="password"
        )
        
        print(f"✅ Created knowledge base: {type(kb).__name__}")
        print(f"   Connected to Neo4j: {kb.driver is not None}")
        print()
        
        # Clear existing data
        kb.clear()
        
        # Create a more realistic code structure
        entities = [
            # FastAPI application files
            CodeEntity(
                id="main_py", name="main.py", type="file", path="./main.py",
                content="from fastapi import FastAPI\nfrom routers import users, items\napp = FastAPI()\napp.include_router(users.router)\napp.include_router(items.router)", 
                language="python", size=200, created_at=datetime.now(), metadata={"framework": "fastapi"}
            ),
            
            # Router files
            CodeEntity(
                id="users_router", name="users.py", type="file", path="./routers/users.py",
                content="from fastapi import APIRouter\nfrom models import User\nfrom database import get_db\nrouter = APIRouter()\n@router.get('/users')\ndef get_users():\n    return []", 
                language="python", size=300, created_at=datetime.now(), metadata={"component": "router"}
            ),
            
            CodeEntity(
                id="items_router", name="items.py", type="file", path="./routers/items.py",
                content="from fastapi import APIRouter\nfrom models import Item\nfrom database import get_db\nrouter = APIRouter()\n@router.get('/items')\ndef get_items():\n    return []", 
                language="python", size=280, created_at=datetime.now(), metadata={"component": "router"}
            ),
            
            # Models
            CodeEntity(
                id="models_py", name="models.py", type="file", path="./models.py",
                content="from sqlalchemy import Column, Integer, String\nfrom database import Base\nclass User(Base):\n    id = Column(Integer, primary_key=True)\n    name = Column(String)\nclass Item(Base):\n    id = Column(Integer, primary_key=True)\n    title = Column(String)", 
                language="python", size=250, created_at=datetime.now(), metadata={"component": "models"}
            ),
            
            # Database
            CodeEntity(
                id="database_py", name="database.py", type="file", path="./database.py",
                content="from sqlalchemy import create_engine\nfrom sqlalchemy.ext.declarative import declarative_base\nfrom sqlalchemy.orm import sessionmaker\nengine = create_engine('sqlite:///app.db')\nBase = declarative_base()\ndef get_db():\n    db = SessionLocal()\n    try:\n        yield db\n    finally:\n        db.close()", 
                language="python", size=350, created_at=datetime.now(), metadata={"component": "database"}
            ),
            
            # Authentication utilities
            CodeEntity(
                id="auth_utils", name="auth_utils.py", type="file", path="./auth_utils.py",
                content="from passlib.context import CryptContext\nfrom datetime import datetime, timedelta\nimport jwt\n\npwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')\nSECRET_KEY = 'your-secret-key'\nALGORITHM = 'HS256'\n\ndef hash_password(password: str) -> str:\n    return pwd_context.hash(password)\n\ndef verify_password(plain_password: str, hashed_password: str) -> bool:\n    return pwd_context.verify(plain_password, hashed_password)\n\ndef create_access_token(data: dict, expires_delta: timedelta = None):\n    to_encode = data.copy()\n    if expires_delta:\n        expire = datetime.utcnow() + expires_delta\n    else:\n        expire = datetime.utcnow() + timedelta(minutes=15)\n    to_encode.update({'exp': expire})\n    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)\n    return encoded_jwt", 
                language="python", size=600, created_at=datetime.now(), metadata={"component": "authentication"}
            ),
            
            # Classes
            CodeEntity(
                id="user_class", name="User", type="class", path="./models.py",
                content="class User(Base):\n    id = Column(Integer, primary_key=True)\n    name = Column(String)", 
                language="python", size=80, created_at=datetime.now(), metadata={"table": "users"}
            ),
            
            CodeEntity(
                id="item_class", name="Item", type="class", path="./models.py",
                content="class Item(Base):\n    id = Column(Integer, primary_key=True)\n    title = Column(String)", 
                language="python", size=75, created_at=datetime.now(), metadata={"table": "items"}
            ),
            
            # Functions
            CodeEntity(
                id="get_users_func", name="get_users", type="function", path="./routers/users.py",
                content="@router.get('/users')\ndef get_users():\n    return []", 
                language="python", size=50, created_at=datetime.now(), metadata={"endpoint": "/users"}
            ),
            
            CodeEntity(
                id="get_items_func", name="get_items", type="function", path="./routers/items.py",
                content="@router.get('/items')\ndef get_items():\n    return []", 
                language="python", size=50, created_at=datetime.now(), metadata={"endpoint": "/items"}
            )
        ]
        
        # Add entities to KB
        print("📝 Adding entities to knowledge base...")
        for entity in entities:
            kb.add_entity(entity)
        
        # Create relationships
        relationships = [
            # Import relationships
            CodeRelationship(
                id="main_imports_users", source_id="main_py", target_id="users_router",
                relationship_type="imports", strength=0.9, metadata={"import_type": "module"}
            ),
            CodeRelationship(
                id="main_imports_items", source_id="main_py", target_id="items_router",
                relationship_type="imports", strength=0.9, metadata={"import_type": "module"}
            ),
            CodeRelationship(
                id="users_imports_models", source_id="users_router", target_id="models_py",
                relationship_type="imports", strength=0.8, metadata={"import_type": "module"}
            ),
            CodeRelationship(
                id="items_imports_models", source_id="items_router", target_id="models_py",
                relationship_type="imports", strength=0.8, metadata={"import_type": "module"}
            ),
            CodeRelationship(
                id="users_imports_database", source_id="users_router", target_id="database_py",
                relationship_type="imports", strength=0.7, metadata={"import_type": "module"}
            ),
            CodeRelationship(
                id="items_imports_database", source_id="items_router", target_id="database_py",
                relationship_type="imports", strength=0.7, metadata={"import_type": "module"}
            ),
            
            # Contains relationships
            CodeRelationship(
                id="models_contains_user", source_id="models_py", target_id="user_class",
                relationship_type="contains", strength=1.0, metadata={"container_type": "file"}
            ),
            CodeRelationship(
                id="models_contains_item", source_id="models_py", target_id="item_class",
                relationship_type="contains", strength=1.0, metadata={"container_type": "file"}
            ),
            CodeRelationship(
                id="users_contains_get_users", source_id="users_router", target_id="get_users_func",
                relationship_type="contains", strength=1.0, metadata={"container_type": "file"}
            ),
            CodeRelationship(
                id="items_contains_get_items", source_id="items_router", target_id="get_items_func",
                relationship_type="contains", strength=1.0, metadata={"container_type": "file"}
            ),
            
            # Uses relationships
            CodeRelationship(
                id="get_users_uses_user", source_id="get_users_func", target_id="user_class",
                relationship_type="uses", strength=0.8, metadata={"usage_type": "model"}
            ),
            CodeRelationship(
                id="get_items_uses_item", source_id="get_items_func", target_id="item_class",
                relationship_type="uses", strength=0.8, metadata={"usage_type": "model"}
            ),
            
            # Similar relationships
            CodeRelationship(
                id="users_similar_items", source_id="users_router", target_id="items_router",
                relationship_type="similar", strength=0.9, metadata={"similarity_type": "structure"}
            ),
            CodeRelationship(
                id="user_similar_item", source_id="user_class", target_id="item_class",
                relationship_type="similar", strength=0.8, metadata={"similarity_type": "model"}
            ),
            
            # Authentication relationships
            CodeRelationship(
                id="users_imports_auth", source_id="users_router", target_id="auth_utils",
                relationship_type="imports", strength=0.8, metadata={"import_type": "authentication"}
            )
        ]
        
        print("🔗 Adding relationships to knowledge base...")
        for rel in relationships:
            kb.add_relationship(rel)
        
        print(f"✅ Added {len(entities)} entities and {len(relationships)} relationships")
        print()
        
        # Test different query scenarios
        print("🔍 Testing Query Scenarios:")
        print("-" * 40)
        
        # Test content searches
        self._test_content_searches(kb)
        
        # Test relationship queries
        self._test_relationship_queries(kb)
        
        # Test enhanced graph features
        self._test_enhanced_graph_features(kb)
        
        # Test question-based queries
        self._test_question_based_queries(kb)
        
        print("✅ Query testing completed!")
        return True
    
    def _test_content_searches(self, kb):
        """Test content-based searches."""
        print("1. Search for FastAPI-related code:")
        fastapi_entities = kb.search_entities("FastAPI")
        for entity in fastapi_entities:
            print(f"   • {entity.name} ({entity.type}) - {entity.path}")
        print()
        
        print("2. Search for router-related code:")
        router_entities = kb.search_entities("router")
        for entity in router_entities[:5]:
            print(f"   • {entity.name} ({entity.type}) - {entity.path}")
        print()
        
        print("3. Search for database-related code:")
        db_entities = kb.search_entities("database")
        for entity in db_entities:
            print(f"   • {entity.name} ({entity.type}) - {entity.path}")
        print()
    
    def _test_relationship_queries(self, kb):
        """Test relationship-based queries."""
        print("4. Find entities related to main.py:")
        main_related = kb.get_related_entities("main_py")
        for entity, rel in main_related:
            print(f"   • {entity.name} ({rel.relationship_type}) - strength: {rel.strength}")
        print()
        
        print("5. Find entities that main.py imports:")
        main_imports = kb.get_related_entities("main_py", relationship_type="imports")
        for entity, rel in main_imports:
            print(f"   • {entity.name} - {entity.path}")
        print()
    
    def _test_enhanced_graph_features(self, kb):
        """Test enhanced graph analytics features."""
        print("6. Find most central entities:")
        central = kb.find_central_entities(limit=5)
        for entity, degree in central:
            print(f"   • {entity.name} (degree: {degree})")
        print()
        
        print("7. Find shortest path from main.py to User class:")
        path = kb.find_shortest_path("main_py", "user_class")
        if path:
            path_names = [e.name for e in path]
            print(f"    Path: {' → '.join(path_names)}")
        else:
            print("    No path found")
        print()
        
        print("8. Find neighborhood of models.py:")
        neighbors = kb.get_entity_neighborhood("models_py", depth=2)
        neighbor_names = [e.name for e in neighbors]
        print(f"    Neighbors: {', '.join(neighbor_names)}")
        print()
    
    def _test_question_based_queries(self, kb):
        """Test question-based queries."""
        print("9. Question-based queries:")
        print("    " + "="*40)
        
        questions = [
            "How does authentication work?",
            "What are the main API endpoints?",
            "How is the database configured?",
            "What models are defined?",
            "How are passwords handled?"
        ]
        
        for i, question in enumerate(questions, 1):
            print(f"    Q{i}: {question}")
            
            # Extract keywords from question
            keywords = self._extract_keywords(question)
            print(f"         Keywords: {', '.join(keywords)}")
            
            # Search for relevant entities
            relevant_entities = []
            for keyword in keywords:
                entities = kb.search_entities(keyword)
                relevant_entities.extend(entities)
            
            # Remove duplicates and get top results
            unique_entities = list({e.id: e for e in relevant_entities}.values())[:3]
            
            print(f"         Found: {', '.join([e.name for e in unique_entities])}")
            
            # Show related entities
            if unique_entities:
                related = kb.get_related_entities(unique_entities[0].id)
                if related:
                    related_names = [e.name for e, _ in related[:2]]
                    print(f"         Related: {', '.join(related_names)}")
            print()
    
    def _extract_keywords(self, question: str) -> list:
        """Extract relevant keywords from a question."""
        keywords = []
        question_lower = question.lower()
        
        # Technical keywords
        tech_terms = [
            'authentication', 'auth', 'login', 'token', 'jwt', 'password',
            'database', 'db', 'model', 'table', 'user', 'endpoint', 'api',
            'router', 'middleware', 'configuration', 'config', 'entry point',
            'registration', 'fastapi', 'sqlalchemy', 'pydantic'
        ]
        
        for term in tech_terms:
            if term in question_lower:
                keywords.append(term)
        
        # Action keywords
        action_terms = ['create', 'get', 'post', 'put', 'delete', 'handle', 'work']
        for term in action_terms:
            if term in question_lower:
                keywords.append(term)
        
        return keywords if keywords else ['main', 'app']


def test_neo4j_connection():
    """Test Neo4j connection configurations."""
    tester = TestNeo4jConnection()
    return tester.test_connection_configs()


def test_neo4j_enhanced():
    """Test enhanced Neo4j features."""
    tester = TestNeo4jEnhanced()
    return tester.test_enhanced_features()


def test_neo4j_queries():
    """Test Neo4j query functionality."""
    tester = TestNeo4jQueries()
    return tester.test_query_functionality()


def run_all_tests():
    """Run all Neo4j tests."""
    print("🧪 Running Comprehensive Neo4j Test Suite")
    print("=" * 60)
    
    tests = [
        ("Connection Tests", test_neo4j_connection),
        ("Enhanced Features Tests", test_neo4j_enhanced),
        ("Query Functionality Tests", test_neo4j_queries)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 40)
        try:
            result = test_func()
            results.append((test_name, result))
            print(f"{'✅ PASSED' if result else '❌ FAILED'}: {test_name}")
        except Exception as e:
            print(f"❌ ERROR: {test_name} - {e}")
            results.append((test_name, False))
    
    print(f"\n🎯 Test Suite Summary:")
    print("=" * 30)
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {status}: {test_name}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    return passed == total


if __name__ == "__main__":
    # Run individual test if specified
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == "connection":
            test_neo4j_connection()
        elif test_name == "enhanced":
            test_neo4j_enhanced()
        elif test_name == "queries":
            test_neo4j_queries()
        else:
            print("Usage: python test_neo4j.py [connection|enhanced|queries]")
    else:
        # Run all tests
        run_all_tests()