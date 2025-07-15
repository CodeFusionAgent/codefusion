"""Code Knowledge Base implementation for CodeFusion."""

import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CodeEntity:
    """Represents a code entity in the knowledge base."""

    id: str
    name: str
    type: str  # "file", "function", "class", "module", "variable"
    path: str
    content: str
    language: str
    size: int
    created_at: datetime
    metadata: Dict[str, Any]


@dataclass
class CodeRelationship:
    """Represents a relationship between code entities."""

    id: str
    source_id: str
    target_id: str
    relationship_type: str  # "imports", "calls", "inherits", "contains", "uses"
    strength: float  # 0.0 to 1.0
    metadata: Dict[str, Any]


@dataclass
class C4Level:
    """C4 architecture level mapping."""

    context: List[CodeEntity]  # System context
    containers: List[CodeEntity]  # Applications/services
    components: List[CodeEntity]  # Modules/packages
    code: List[CodeEntity]  # Classes/functions


class CodeKB(ABC):
    """Abstract base class for Code Knowledge Base."""

    def __init__(self, storage_path: str):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._entities: Dict[str, CodeEntity] = {}
        self._relationships: Dict[str, CodeRelationship] = {}
        self._c4_mapping: Optional[C4Level] = None

    @abstractmethod
    def add_entity(self, entity: CodeEntity) -> None:
        """Add a code entity to the knowledge base."""
        pass

    @abstractmethod
    def add_relationship(self, relationship: CodeRelationship) -> None:
        """Add a relationship between entities."""
        pass

    @abstractmethod
    def get_entity(self, entity_id: str) -> Optional[CodeEntity]:
        """Retrieve an entity by ID."""
        pass

    @abstractmethod
    def search_entities(
        self, query: str, entity_type: Optional[str] = None
    ) -> List[CodeEntity]:
        """Search for entities matching the query."""
        pass

    @abstractmethod
    def get_related_entities(
        self, entity_id: str, relationship_type: Optional[str] = None
    ) -> List[Tuple[CodeEntity, CodeRelationship]]:
        """Get entities related to the given entity."""
        pass

    @abstractmethod
    def save(self) -> None:
        """Persist the knowledge base to storage."""
        pass

    @abstractmethod
    def load(self) -> None:
        """Load the knowledge base from storage."""
        pass

    def create_c4_mapping(self) -> C4Level:
        """Create C4 architecture mapping from entities."""
        context = []
        containers = []
        components = []
        code = []

        for entity in self._entities.values():
            if entity.type == "project":
                context.append(entity)
            elif entity.type in ["application", "service", "module"]:
                containers.append(entity)
            elif entity.type in ["package", "namespace", "directory"]:
                components.append(entity)
            elif entity.type in ["file", "class", "function"]:
                code.append(entity)

        self._c4_mapping = C4Level(
            context=context, containers=containers, components=components, code=code
        )
        return self._c4_mapping

    def get_c4_mapping(self) -> Optional[C4Level]:
        """Get the C4 architecture mapping."""
        if self._c4_mapping is None:
            return self.create_c4_mapping()
        return self._c4_mapping

    def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge base statistics."""
        entity_types = {}
        relationship_types = {}

        for entity in self._entities.values():
            entity_types[entity.type] = entity_types.get(entity.type, 0) + 1

        for rel in self._relationships.values():
            relationship_types[rel.relationship_type] = (
                relationship_types.get(rel.relationship_type, 0) + 1
            )

        return {
            "total_entities": len(self._entities),
            "total_relationships": len(self._relationships),
            "entity_types": entity_types,
            "relationship_types": relationship_types,
            "storage_path": str(self.storage_path),
        }


class TextBasedKB(CodeKB):
    """Text/JSON-based implementation of Code Knowledge Base."""

    def __init__(self, storage_path: str):
        super().__init__(storage_path)
        self.entities_file = self.storage_path / "entities.json"
        self.relationships_file = self.storage_path / "relationships.json"
        self.c4_file = self.storage_path / "c4_mapping.json"

        # Try to load existing data
        self.load()

    def add_entity(self, entity: CodeEntity) -> None:
        """Add a code entity to the knowledge base."""
        self._entities[entity.id] = entity

    def add_relationship(self, relationship: CodeRelationship) -> None:
        """Add a relationship between entities."""
        self._relationships[relationship.id] = relationship

    def get_entity(self, entity_id: str) -> Optional[CodeEntity]:
        """Retrieve an entity by ID."""
        return self._entities.get(entity_id)

    def search_entities(
        self, query: str, entity_type: Optional[str] = None
    ) -> List[CodeEntity]:
        """Search for entities matching the query."""
        results = []
        query_lower = query.lower()

        for entity in self._entities.values():
            # Filter by type if specified
            if entity_type and entity.type != entity_type:
                continue

            # Search in name, path, and content
            if (
                query_lower in entity.name.lower()
                or query_lower in entity.path.lower()
                or query_lower in entity.content.lower()
            ):
                results.append(entity)

        return results

    def get_related_entities(
        self, entity_id: str, relationship_type: Optional[str] = None
    ) -> List[Tuple[CodeEntity, CodeRelationship]]:
        """Get entities related to the given entity."""
        results = []

        for rel in self._relationships.values():
            if rel.source_id == entity_id or rel.target_id == entity_id:
                if relationship_type and rel.relationship_type != relationship_type:
                    continue

                # Get the related entity (not the source entity)
                related_id = (
                    rel.target_id if rel.source_id == entity_id else rel.source_id
                )
                related_entity = self._entities.get(related_id)

                if related_entity:
                    results.append((related_entity, rel))

        return results

    def save(self) -> None:
        """Persist the knowledge base to storage."""
        # Save entities
        entities_data = {}
        for entity_id, entity in self._entities.items():
            entity_dict = asdict(entity)
            entity_dict["created_at"] = entity.created_at.isoformat()
            entities_data[entity_id] = entity_dict

        with open(self.entities_file, "w", encoding="utf-8") as f:
            json.dump(entities_data, f, indent=2, ensure_ascii=False)

        # Save relationships
        relationships_data = {}
        for rel_id, rel in self._relationships.items():
            relationships_data[rel_id] = asdict(rel)

        with open(self.relationships_file, "w", encoding="utf-8") as f:
            json.dump(relationships_data, f, indent=2, ensure_ascii=False)

        # Note: C4 mapping is dynamically generated, not saved to disk

    def load(self) -> None:
        """Load the knowledge base from storage."""
        # Load entities
        if self.entities_file.exists():
            with open(self.entities_file, "r", encoding="utf-8") as f:
                entities_data = json.load(f)

            for entity_id, entity_dict in entities_data.items():
                entity_dict["created_at"] = datetime.fromisoformat(
                    entity_dict["created_at"]
                )
                self._entities[entity_id] = CodeEntity(**entity_dict)

        # Load relationships
        if self.relationships_file.exists():
            with open(self.relationships_file, "r", encoding="utf-8") as f:
                relationships_data = json.load(f)

            for rel_id, rel_dict in relationships_data.items():
                self._relationships[rel_id] = CodeRelationship(**rel_dict)

    def clear(self) -> None:
        """Clear all data from the knowledge base."""
        self._entities.clear()
        self._relationships.clear()
        self._c4_mapping = None

        # Remove files if they exist
        for file_path in [self.entities_file, self.relationships_file, self.c4_file]:
            if file_path.exists():
                file_path.unlink()


class Neo4jKB(CodeKB):
    """Neo4j-based implementation of Code Knowledge Base."""

    def __init__(self, storage_path: str, uri: str, user: str, password: str):
        super().__init__(storage_path)
        self.uri = uri
        self.user = user
        self.password = password
        self.driver = None

        try:
            import neo4j

            self.neo4j = neo4j
            self.NEO4J_AVAILABLE = True
        except ImportError:
            self.neo4j = None
            self.NEO4J_AVAILABLE = False
            print("Warning: neo4j driver not available. Using in-memory fallback.")

        self._connect()

    def _connect(self):
        """Connect to Neo4j database."""
        if not self.NEO4J_AVAILABLE:
            return

        try:
            self.driver = self.neo4j.GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            print(f"✓ Connected to Neo4j at {self.uri}")
        except Exception as e:
            print(f"Warning: Could not connect to Neo4j: {e}")
            print("Using in-memory fallback storage")
            self.driver = None

    def add_entity(self, entity: CodeEntity) -> None:
        """Add a code entity to Neo4j."""
        self._entities[entity.id] = entity

        if self.driver:
            with self.driver.session() as session:
                session.run(
                    """
                    MERGE (e:CodeEntity {id: $id})
                    SET e.name = $name,
                        e.type = $type,
                        e.path = $path,
                        e.content = $content,
                        e.language = $language,
                        e.size = $size,
                        e.created_at = $created_at,
                        e.metadata = $metadata
                    """,
                    id=entity.id,
                    name=entity.name,
                    type=entity.type,
                    path=entity.path,
                    content=entity.content[:1000],  # Limit content size
                    language=entity.language,
                    size=entity.size,
                    created_at=entity.created_at.isoformat(),
                    metadata=json.dumps(entity.metadata),
                )

    def add_relationship(self, relationship: CodeRelationship) -> None:
        """Add a relationship to Neo4j."""
        self._relationships[relationship.id] = relationship

        if self.driver:
            with self.driver.session() as session:
                session.run(
                    """
                    MATCH (source:CodeEntity {id: $source_id})
                    MATCH (target:CodeEntity {id: $target_id})
                    MERGE (source)-[r:RELATES {
                        id: $rel_id,
                        type: $rel_type,
                        strength: $strength,
                        metadata: $metadata
                    }]->(target)
                    """,
                    source_id=relationship.source_id,
                    target_id=relationship.target_id,
                    rel_id=relationship.id,
                    rel_type=relationship.relationship_type,
                    strength=relationship.strength,
                    metadata=json.dumps(relationship.metadata),
                )

    def get_entity(self, entity_id: str) -> Optional[CodeEntity]:
        """Retrieve an entity by ID."""
        if entity_id in self._entities:
            return self._entities[entity_id]

        if self.driver:
            with self.driver.session() as session:
                result = session.run(
                    "MATCH (e:CodeEntity {id: $id}) RETURN e", id=entity_id
                )
                record = result.single()
                if record:
                    node = record["e"]
                    entity = CodeEntity(
                        id=node["id"],
                        name=node["name"],
                        type=node["type"],
                        path=node["path"],
                        content=node["content"],
                        language=node["language"],
                        size=node["size"],
                        created_at=datetime.fromisoformat(node["created_at"]),
                        metadata=(
                            json.loads(node["metadata"]) if node["metadata"] else {}
                        ),
                    )
                    self._entities[entity_id] = entity
                    return entity

        return None

    def search_entities(
        self, query: str, entity_type: Optional[str] = None
    ) -> List[CodeEntity]:
        """Search for entities in Neo4j."""
        if not self.driver:
            # Fallback to in-memory search
            results = []
            query_lower = query.lower()
            for entity in self._entities.values():
                if entity_type and entity.type != entity_type:
                    continue
                if (
                    query_lower in entity.name.lower()
                    or query_lower in entity.path.lower()
                    or query_lower in entity.content.lower()
                ):
                    results.append(entity)
            return results

        # Use Neo4j full-text search
        with self.driver.session() as session:
            cypher = """
            MATCH (e:CodeEntity)
            WHERE toLower(e.name) CONTAINS toLower($query)
               OR toLower(e.path) CONTAINS toLower($query)
               OR toLower(e.content) CONTAINS toLower($query)
            """

            if entity_type:
                cypher += " AND e.type = $entity_type"

            cypher += " RETURN e LIMIT 50"

            params = {"query": query}
            if entity_type:
                params["entity_type"] = entity_type

            result = session.run(cypher, params)

            entities = []
            for record in result:
                node = record["e"]
                entity = CodeEntity(
                    id=node["id"],
                    name=node["name"],
                    type=node["type"],
                    path=node["path"],
                    content=node["content"],
                    language=node["language"],
                    size=node["size"],
                    created_at=datetime.fromisoformat(node["created_at"]),
                    metadata=json.loads(node["metadata"]) if node["metadata"] else {},
                )
                entities.append(entity)
                self._entities[entity.id] = entity

            return entities

    def get_related_entities(
        self, entity_id: str, relationship_type: Optional[str] = None
    ) -> List[Tuple[CodeEntity, CodeRelationship]]:
        """Get entities related to the given entity in Neo4j."""
        if not self.driver:
            # Fallback to in-memory relationships
            results = []
            for rel in self._relationships.values():
                if rel.source_id == entity_id or rel.target_id == entity_id:
                    if relationship_type and rel.relationship_type != relationship_type:
                        continue

                    related_id = (
                        rel.target_id if rel.source_id == entity_id else rel.source_id
                    )
                    related_entity = self._entities.get(related_id)

                    if related_entity:
                        results.append((related_entity, rel))
            return results

        # Use Neo4j graph traversal
        with self.driver.session() as session:
            cypher = """
            MATCH (source:CodeEntity {id: $entity_id})-[r:RELATES]-(target:CodeEntity)
            """

            if relationship_type:
                cypher += " WHERE r.type = $relationship_type"

            cypher += " RETURN target, r"

            params = {"entity_id": entity_id}
            if relationship_type:
                params["relationship_type"] = relationship_type

            result = session.run(cypher, params)

            related = []
            for record in result:
                target_node = record["target"]
                rel_data = record["r"]

                # Create entity
                entity = CodeEntity(
                    id=target_node["id"],
                    name=target_node["name"],
                    type=target_node["type"],
                    path=target_node["path"],
                    content=target_node["content"],
                    language=target_node["language"],
                    size=target_node["size"],
                    created_at=datetime.fromisoformat(target_node["created_at"]),
                    metadata=(
                        json.loads(target_node["metadata"])
                        if target_node["metadata"]
                        else {}
                    ),
                )

                # Create relationship
                relationship = CodeRelationship(
                    id=rel_data["id"],
                    source_id=entity_id,
                    target_id=target_node["id"],
                    relationship_type=rel_data["type"],
                    strength=rel_data["strength"],
                    metadata=(
                        json.loads(rel_data["metadata"]) if rel_data["metadata"] else {}
                    ),
                )

                related.append((entity, relationship))
                self._entities[entity.id] = entity
                self._relationships[relationship.id] = relationship

            return related

    def save(self) -> None:
        """Save knowledge base (Neo4j handles persistence automatically)."""
        if not self.driver:
            # Save to JSON files as fallback
            super().save()
        # Neo4j automatically persists data
        pass

    def load(self) -> None:
        """Load knowledge base from Neo4j."""
        if not self.driver:
            # Load from JSON files as fallback
            super().load()
            return

        # Load all entities and relationships from Neo4j
        with self.driver.session() as session:
            # Load entities
            result = session.run("MATCH (e:CodeEntity) RETURN e")
            for record in result:
                node = record["e"]
                entity = CodeEntity(
                    id=node["id"],
                    name=node["name"],
                    type=node["type"],
                    path=node["path"],
                    content=node["content"],
                    language=node["language"],
                    size=node["size"],
                    created_at=datetime.fromisoformat(node["created_at"]),
                    metadata=json.loads(node["metadata"]) if node["metadata"] else {},
                )
                self._entities[entity.id] = entity

            # Load relationships
            result = session.run("MATCH ()-[r:RELATES]->() RETURN r")
            for record in result:
                rel_data = record["r"]
                relationship = CodeRelationship(
                    id=rel_data["id"],
                    source_id=rel_data.start_node["id"],
                    target_id=rel_data.end_node["id"],
                    relationship_type=rel_data["type"],
                    strength=rel_data["strength"],
                    metadata=(
                        json.loads(rel_data["metadata"]) if rel_data["metadata"] else {}
                    ),
                )
                self._relationships[relationship.id] = relationship

    def clear(self) -> None:
        """Clear all data from Neo4j."""
        self._entities.clear()
        self._relationships.clear()
        self._c4_mapping = None

        if self.driver:
            with self.driver.session() as session:
                session.run("MATCH (n) DETACH DELETE n")

    def close(self) -> None:
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()

    def get_graph_stats(self) -> Dict[str, Any]:
        """Get Neo4j-specific statistics."""
        if not self.driver:
            return self.get_statistics()

        with self.driver.session() as session:
            # Get node count by type
            result = session.run(
                """
                MATCH (n:CodeEntity)
                RETURN n.type as type, count(n) as count
            """
            )
            entity_types = {record["type"]: record["count"] for record in result}

            # Get relationship count by type
            result = session.run(
                """
                MATCH ()-[r:RELATES]->()
                RETURN r.type as type, count(r) as count
            """
            )
            relationship_types = {record["type"]: record["count"] for record in result}

            # Get total counts
            result = session.run("MATCH (n:CodeEntity) RETURN count(n) as total")
            total_entities = result.single()["total"]

            result = session.run("MATCH ()-[r:RELATES]->() RETURN count(r) as total")
            total_relationships = result.single()["total"]

            return {
                "total_entities": total_entities,
                "total_relationships": total_relationships,
                "entity_types": entity_types,
                "relationship_types": relationship_types,
                "storage_path": str(self.storage_path),
                "neo4j_uri": self.uri,
                "neo4j_available": self.NEO4J_AVAILABLE,
                "connected": self.driver is not None,
            }

    def find_shortest_path(
        self, source_id: str, target_id: str, max_depth: int = 5
    ) -> Optional[List[CodeEntity]]:
        """Find the shortest path between two entities using graph traversal."""
        if not self.driver:
            # Fallback to simple breadth-first search in memory
            return self._find_path_in_memory(source_id, target_id, max_depth)

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH path = shortestPath((source:CodeEntity {id: $source_id})-[*1..%d]-(target:CodeEntity {id: $target_id}))
                RETURN path
                """
                % max_depth,
                source_id=source_id,
                target_id=target_id,
            )

            record = result.single()
            if not record:
                return None

            path = record["path"]
            path_entities = []

            for node in path.nodes:
                entity = self._node_to_entity(node)
                if entity:
                    path_entities.append(entity)

            return path_entities

    def find_central_entities(self, limit: int = 10) -> List[Tuple[CodeEntity, int]]:
        """Find most central entities using degree centrality."""
        if not self.driver:
            return self._find_central_entities_in_memory(limit)

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:CodeEntity)
                WITH e, COUNT { (e)-[:RELATES]-() } as degree
                WHERE degree > 0
                RETURN e, degree
                ORDER BY degree DESC
                LIMIT $limit
                """,
                limit=limit,
            )

            central_entities = []
            for record in result:
                entity = self._node_to_entity(record["e"])
                if entity:
                    central_entities.append((entity, record["degree"]))

            return central_entities

    def find_entity_clusters(self, min_cluster_size: int = 3) -> List[List[CodeEntity]]:
        """Find clusters of closely related entities."""
        if not self.driver:
            return self._find_clusters_in_memory(min_cluster_size)

        with self.driver.session() as session:
            # Find strongly connected components
            result = session.run(
                """
                MATCH (e:CodeEntity)
                WITH e, [(e)-[:RELATES*1..2]-(connected) | connected] as connected_entities
                WHERE size(connected_entities) >= $min_size
                RETURN e, connected_entities
                """,
                min_size=min_cluster_size,
            )

            clusters = []
            processed_entities = set()

            for record in result:
                main_entity = self._node_to_entity(record["e"])
                if not main_entity or main_entity.id in processed_entities:
                    continue

                cluster = [main_entity]
                processed_entities.add(main_entity.id)

                for connected_node in record["connected_entities"]:
                    connected_entity = self._node_to_entity(connected_node)
                    if (
                        connected_entity
                        and connected_entity.id not in processed_entities
                    ):
                        cluster.append(connected_entity)
                        processed_entities.add(connected_entity.id)

                if len(cluster) >= min_cluster_size:
                    clusters.append(cluster)

            return clusters

    def analyze_architectural_patterns(self) -> List[Dict[str, Any]]:
        """Analyze architectural patterns in the codebase."""
        if not self.driver:
            return self._analyze_patterns_in_memory()

        patterns = []

        with self.driver.session() as session:
            # Pattern 1: Hub entities (high fan-out)
            result = session.run(
                """
                MATCH (hub:CodeEntity)-[:RELATES]->(connected:CodeEntity)
                WITH hub, count(connected) as connections
                WHERE connections > 5
                RETURN hub, connections
                ORDER BY connections DESC
                LIMIT 5
                """
            )

            hubs = []
            for record in result:
                entity = self._node_to_entity(record["hub"])
                if entity:
                    hubs.append(
                        {"entity": entity, "connections": record["connections"]}
                    )

            if hubs:
                patterns.append(
                    {
                        "pattern_type": "hub_entities",
                        "description": "Entities with high fan-out (potential bottlenecks)",
                        "entities": hubs,
                    }
                )

            # Pattern 2: Circular dependencies
            result = session.run(
                """
                MATCH path = (a:CodeEntity)-[:RELATES*2..4]->(a)
                WHERE all(r in relationships(path) WHERE r.type IN ['imports', 'calls', 'uses'])
                RETURN path
                LIMIT 10
                """
            )

            circular_deps = []
            for record in result:
                path = record["path"]
                entities = []
                for node in path.nodes:
                    entity = self._node_to_entity(node)
                    if entity:
                        entities.append(entity)
                if entities:
                    circular_deps.append(entities)

            if circular_deps:
                patterns.append(
                    {
                        "pattern_type": "circular_dependencies",
                        "description": "Circular dependencies that may indicate design issues",
                        "cycles": circular_deps,
                    }
                )

        return patterns

    def get_entity_neighborhood(
        self, entity_id: str, depth: int = 2
    ) -> List[CodeEntity]:
        """Get all entities within a certain depth from the given entity."""
        if not self.driver:
            return self._get_neighborhood_in_memory(entity_id, depth)

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (center:CodeEntity {id: $entity_id})-[:RELATES*1..%d]-(neighbor:CodeEntity)
                RETURN DISTINCT neighbor
                """
                % depth,
                entity_id=entity_id,
            )

            neighbors = []
            for record in result:
                entity = self._node_to_entity(record["neighbor"])
                if entity:
                    neighbors.append(entity)

            return neighbors

    def find_similar_entities(
        self, entity_id: str, similarity_threshold: float = 0.7
    ) -> List[Tuple[CodeEntity, float]]:
        """Find entities similar to the given entity."""
        if not self.driver:
            return self._find_similar_in_memory(entity_id, similarity_threshold)

        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (source:CodeEntity {id: $entity_id})-[r:RELATES {type: 'similar'}]-(similar:CodeEntity)
                WHERE r.strength >= $threshold
                RETURN similar, r.strength as similarity
                ORDER BY similarity DESC
                LIMIT 10
                """,
                entity_id=entity_id,
                threshold=similarity_threshold,
            )

            similar_entities = []
            for record in result:
                entity = self._node_to_entity(record["similar"])
                if entity:
                    similar_entities.append((entity, record["similarity"]))

            return similar_entities

    def _node_to_entity(self, node) -> Optional[CodeEntity]:
        """Convert Neo4j node to CodeEntity."""
        try:
            return CodeEntity(
                id=node["id"],
                name=node["name"],
                type=node["type"],
                path=node["path"],
                content=node["content"],
                language=node["language"],
                size=node["size"],
                created_at=datetime.fromisoformat(node["created_at"]),
                metadata=json.loads(node["metadata"]) if node["metadata"] else {},
            )
        except Exception:
            return None

    def _find_path_in_memory(
        self, source_id: str, target_id: str, max_depth: int
    ) -> Optional[List[CodeEntity]]:
        """Fallback breadth-first search in memory."""
        if source_id not in self._entities or target_id not in self._entities:
            return None

        # Simple BFS implementation
        queue = [(source_id, [source_id])]
        visited = set()

        while queue:
            current_id, path = queue.pop(0)

            if current_id == target_id:
                return [self._entities[eid] for eid in path if eid in self._entities]

            if current_id in visited or len(path) > max_depth:
                continue

            visited.add(current_id)

            # Find related entities
            for rel in self._relationships.values():
                next_id = None
                if rel.source_id == current_id:
                    next_id = rel.target_id
                elif rel.target_id == current_id:
                    next_id = rel.source_id

                if next_id and next_id not in visited:
                    queue.append((next_id, path + [next_id]))

        return None

    def _find_central_entities_in_memory(
        self, limit: int
    ) -> List[Tuple[CodeEntity, int]]:
        """Fallback centrality calculation in memory."""
        entity_degrees = {}

        for rel in self._relationships.values():
            entity_degrees[rel.source_id] = entity_degrees.get(rel.source_id, 0) + 1
            entity_degrees[rel.target_id] = entity_degrees.get(rel.target_id, 0) + 1

        # Sort by degree and return top entities
        sorted_entities = sorted(
            entity_degrees.items(), key=lambda x: x[1], reverse=True
        )

        central_entities = []
        for entity_id, degree in sorted_entities[:limit]:
            if entity_id in self._entities:
                central_entities.append((self._entities[entity_id], degree))

        return central_entities

    def _find_clusters_in_memory(self, min_cluster_size: int) -> List[List[CodeEntity]]:
        """Fallback clustering in memory."""
        # Simple connected components approach
        visited = set()
        clusters = []

        for entity_id in self._entities:
            if entity_id in visited:
                continue

            # Find connected component
            component = []
            stack = [entity_id]

            while stack:
                current_id = stack.pop()
                if current_id in visited:
                    continue

                visited.add(current_id)
                component.append(self._entities[current_id])

                # Find neighbors
                for rel in self._relationships.values():
                    neighbor_id = None
                    if rel.source_id == current_id:
                        neighbor_id = rel.target_id
                    elif rel.target_id == current_id:
                        neighbor_id = rel.source_id

                    if neighbor_id and neighbor_id not in visited:
                        stack.append(neighbor_id)

            if len(component) >= min_cluster_size:
                clusters.append(component)

        return clusters

    def _analyze_patterns_in_memory(self) -> List[Dict[str, Any]]:
        """Fallback pattern analysis in memory."""
        patterns = []

        # Find hub entities
        entity_connections = {}
        for rel in self._relationships.values():
            entity_connections[rel.source_id] = (
                entity_connections.get(rel.source_id, 0) + 1
            )

        hubs = []
        for entity_id, connections in entity_connections.items():
            if connections > 5 and entity_id in self._entities:
                hubs.append(
                    {"entity": self._entities[entity_id], "connections": connections}
                )

        if hubs:
            patterns.append(
                {
                    "pattern_type": "hub_entities",
                    "description": "Entities with high fan-out (potential bottlenecks)",
                    "entities": sorted(
                        hubs, key=lambda x: x["connections"], reverse=True
                    )[:5],
                }
            )

        return patterns

    def _get_neighborhood_in_memory(
        self, entity_id: str, depth: int
    ) -> List[CodeEntity]:
        """Fallback neighborhood search in memory."""
        if entity_id not in self._entities:
            return []

        neighbors = set()
        current_level = {entity_id}

        for _ in range(depth):
            next_level = set()
            for current_id in current_level:
                for rel in self._relationships.values():
                    neighbor_id = None
                    if rel.source_id == current_id:
                        neighbor_id = rel.target_id
                    elif rel.target_id == current_id:
                        neighbor_id = rel.source_id

                    if neighbor_id and neighbor_id not in neighbors:
                        next_level.add(neighbor_id)
                        neighbors.add(neighbor_id)

            current_level = next_level

        return [self._entities[eid] for eid in neighbors if eid in self._entities]

    def _find_similar_in_memory(
        self, entity_id: str, threshold: float
    ) -> List[Tuple[CodeEntity, float]]:
        """Fallback similarity search in memory."""
        similar_entities = []

        for rel in self._relationships.values():
            if rel.relationship_type == "similar" and rel.strength >= threshold:
                similar_id = None
                if rel.source_id == entity_id:
                    similar_id = rel.target_id
                elif rel.target_id == entity_id:
                    similar_id = rel.source_id

                if similar_id and similar_id in self._entities:
                    similar_entities.append((self._entities[similar_id], rel.strength))

        return sorted(similar_entities, key=lambda x: x[1], reverse=True)[:10]


def create_knowledge_base(kb_type: str, storage_path: str, **kwargs) -> CodeKB:
    """Factory function to create a knowledge base instance."""
    if kb_type == "text":
        return TextBasedKB(storage_path)
    elif kb_type == "neo4j":
        return Neo4jKB(
            storage_path=storage_path,
            uri=kwargs.get("uri"),
            user=kwargs.get("user"),
            password=kwargs.get("password"),
        )
    elif kb_type == "vector":
        from .vector_kb import VectorKB

        return VectorKB(
            storage_path=storage_path,
            embedding_model=kwargs.get("embedding_model", "all-MiniLM-L6-v2"),
        )
    else:
        raise ValueError(f"Unsupported knowledge base type: {kb_type}")
