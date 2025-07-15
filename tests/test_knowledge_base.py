"""Tests for knowledge base functionality."""

import shutil
import tempfile
from datetime import datetime

import pytest

from cf.kb.knowledge_base import (
    CodeEntity,
    CodeRelationship,
    TextBasedKB,
    create_knowledge_base,
)


class TestCodeEntity:
    """Test cases for CodeEntity class."""

    def test_entity_creation(self):
        """Test creating a code entity."""
        entity = CodeEntity(
            id="test_id",
            name="TestClass",
            type="class",
            path="test.py",
            content="class TestClass: pass",
            language="python",
            size=20,
            created_at=datetime.now(),
            metadata={"line": 1},
        )

        assert entity.id == "test_id"
        assert entity.name == "TestClass"
        assert entity.type == "class"
        assert entity.path == "test.py"
        assert entity.language == "python"
        assert entity.size == 20
        assert "line" in entity.metadata


class TestCodeRelationship:
    """Test cases for CodeRelationship class."""

    def test_relationship_creation(self):
        """Test creating a code relationship."""
        relationship = CodeRelationship(
            id="rel_id",
            source_id="entity1",
            target_id="entity2",
            relationship_type="imports",
            strength=0.8,
            metadata={"line": 5},
        )

        assert relationship.id == "rel_id"
        assert relationship.source_id == "entity1"
        assert relationship.target_id == "entity2"
        assert relationship.relationship_type == "imports"
        assert relationship.strength == 0.8


class TestTextBasedKB:
    """Test cases for TextBasedKB class."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.kb = TextBasedKB(self.temp_dir)

    def teardown_method(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir)

    def test_add_entity(self):
        """Test adding an entity to the knowledge base."""
        entity = CodeEntity(
            id="test_entity",
            name="TestFunction",
            type="function",
            path="test.py",
            content="def test_function(): pass",
            language="python",
            size=25,
            created_at=datetime.now(),
            metadata={},
        )

        self.kb.add_entity(entity)

        retrieved = self.kb.get_entity("test_entity")
        assert retrieved is not None
        assert retrieved.name == "TestFunction"
        assert retrieved.type == "function"

    def test_add_relationship(self):
        """Test adding a relationship to the knowledge base."""
        # Add entities first
        entity1 = CodeEntity(
            id="entity1",
            name="Class1",
            type="class",
            path="test1.py",
            content="",
            language="python",
            size=0,
            created_at=datetime.now(),
            metadata={},
        )
        entity2 = CodeEntity(
            id="entity2",
            name="Class2",
            type="class",
            path="test2.py",
            content="",
            language="python",
            size=0,
            created_at=datetime.now(),
            metadata={},
        )

        self.kb.add_entity(entity1)
        self.kb.add_entity(entity2)

        # Add relationship
        relationship = CodeRelationship(
            id="rel1",
            source_id="entity1",
            target_id="entity2",
            relationship_type="imports",
            strength=1.0,
            metadata={},
        )

        self.kb.add_relationship(relationship)

        # Test relationship retrieval
        related = self.kb.get_related_entities("entity1")
        assert len(related) == 1
        assert related[0][0].id == "entity2"
        assert related[0][1].relationship_type == "imports"

    def test_search_entities(self):
        """Test searching for entities."""
        entity1 = CodeEntity(
            id="e1",
            name="DatabaseManager",
            type="class",
            path="db.py",
            content="class DatabaseManager: ...",
            language="python",
            size=50,
            created_at=datetime.now(),
            metadata={},
        )
        entity2 = CodeEntity(
            id="e2",
            name="UserController",
            type="class",
            path="user.py",
            content="class UserController: ...",
            language="python",
            size=30,
            created_at=datetime.now(),
            metadata={},
        )

        self.kb.add_entity(entity1)
        self.kb.add_entity(entity2)

        # Search by name
        results = self.kb.search_entities("Database")
        assert len(results) == 1
        assert results[0].name == "DatabaseManager"

        # Search by type
        results = self.kb.search_entities("class", entity_type="class")
        assert len(results) == 2

    def test_save_and_load(self):
        """Test saving and loading the knowledge base."""
        entity = CodeEntity(
            id="persistent_entity",
            name="PersistentClass",
            type="class",
            path="persist.py",
            content="class PersistentClass: pass",
            language="python",
            size=25,
            created_at=datetime.now(),
            metadata={},
        )

        self.kb.add_entity(entity)
        self.kb.save()

        # Create new KB instance and load
        new_kb = TextBasedKB(self.temp_dir)

        retrieved = new_kb.get_entity("persistent_entity")
        assert retrieved is not None
        assert retrieved.name == "PersistentClass"

    def test_get_statistics(self):
        """Test getting knowledge base statistics."""
        # Add some test data
        for i in range(3):
            entity = CodeEntity(
                id=f"entity_{i}",
                name=f"Entity{i}",
                type="class",
                path=f"test{i}.py",
                content="",
                language="python",
                size=0,
                created_at=datetime.now(),
                metadata={},
            )
            self.kb.add_entity(entity)

        stats = self.kb.get_statistics()

        assert stats["total_entities"] == 3
        assert stats["entity_types"]["class"] == 3
        assert "storage_path" in stats

    def test_clear(self):
        """Test clearing the knowledge base."""
        entity = CodeEntity(
            id="temp_entity",
            name="TempClass",
            type="class",
            path="temp.py",
            content="",
            language="python",
            size=0,
            created_at=datetime.now(),
            metadata={},
        )

        self.kb.add_entity(entity)
        assert self.kb.get_entity("temp_entity") is not None

        self.kb.clear()
        assert self.kb.get_entity("temp_entity") is None
        assert len(self.kb._entities) == 0


class TestKnowledgeBaseFactory:
    """Test cases for knowledge base factory function."""

    def test_create_text_kb(self):
        """Test creating a text-based knowledge base."""
        with tempfile.TemporaryDirectory() as temp_dir:
            kb = create_knowledge_base("text", temp_dir)
            assert isinstance(kb, TextBasedKB)

    def test_create_unsupported_kb(self):
        """Test creating an unsupported knowledge base type."""
        with pytest.raises(ValueError):
            create_knowledge_base("unsupported", "/tmp")
