"""Vector database implementation for semantic code search."""

import json
import pickle
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import hashlib

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None

from .knowledge_base import CodeKB, CodeEntity, CodeRelationship
from ..exceptions import KnowledgeBaseError


@dataclass
class CodeEmbedding:
    """Represents a code entity with its vector embedding."""
    entity_id: str
    vector: np.ndarray
    metadata: Dict[str, Any]
    created_at: datetime


class EmbeddingGenerator:
    """Generates embeddings for code entities."""
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """Load the embedding model."""
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            print(f"Warning: sentence-transformers not available. Using hash-based embeddings for demo.")
            self.model = None
            return
        
        try:
            self.model = SentenceTransformer(self.model_name)
        except Exception as e:
            # Fallback to simple hash-based embeddings for demo
            print(f"Warning: Could not load embedding model {self.model_name}: {e}")
            print("Using simple hash-based embeddings for demo")
            self.model = None
    
    def generate_embedding(self, entity: CodeEntity) -> np.ndarray:
        """Generate embedding for a code entity."""
        # Create text representation of the code entity
        text = self._entity_to_text(entity)
        
        if self.model is not None:
            # Use sentence transformer
            embedding = self.model.encode(text)
            return embedding.astype(np.float32)
        else:
            # Fallback: Simple hash-based embedding for demo
            return self._hash_based_embedding(text)
    
    def _entity_to_text(self, entity: CodeEntity) -> str:
        """Convert code entity to text for embedding."""
        # Combine different aspects of the entity
        parts = [
            f"Type: {entity.type}",
            f"Name: {entity.name}",
            f"Language: {entity.language}",
            f"Path: {entity.path}",
            f"Content: {entity.content[:500]}"  # First 500 chars
        ]
        
        # Add metadata if available
        if entity.metadata:
            for key, value in entity.metadata.items():
                parts.append(f"{key}: {value}")
        
        return " ".join(parts)
    
    def _hash_based_embedding(self, text: str, dim: int = 384) -> np.ndarray:
        """Create a simple hash-based embedding for demo purposes."""
        # Create multiple hash values to simulate a vector
        hashes = []
        for i in range(dim // 4):  # 4 bytes per hash
            hash_input = f"{text}_{i}".encode()
            hash_val = hashlib.md5(hash_input).hexdigest()
            # Convert hex to int and normalize
            int_val = int(hash_val[:8], 16)
            hashes.append(int_val)
        
        # Convert to numpy array and normalize
        embedding = np.array(hashes, dtype=np.float32)
        embedding = embedding / np.linalg.norm(embedding)
        
        # Pad or truncate to exact dimension
        if len(embedding) < dim:
            padding = np.zeros(dim - len(embedding), dtype=np.float32)
            embedding = np.concatenate([embedding, padding])
        else:
            embedding = embedding[:dim]
        
        return embedding


class VectorKB(CodeKB):
    """Vector database implementation using FAISS for semantic search."""
    
    def __init__(self, storage_path: str, embedding_model: str = "all-MiniLM-L6-v2"):
        super().__init__(storage_path)
        self.embedding_model = embedding_model
        self.embedding_generator = EmbeddingGenerator(embedding_model)
        self.dimension = 384  # Default dimension for MiniLM
        
        # FAISS index
        self.index = None
        self.embeddings: Dict[str, CodeEmbedding] = {}
        self.entity_id_to_index: Dict[str, int] = {}
        self.index_to_entity_id: Dict[int, str] = {}
        
        # File paths
        self.entities_file = self.storage_path / "entities.json"
        self.embeddings_file = self.storage_path / "embeddings.pkl"
        self.index_file = self.storage_path / "faiss.index"
        
        self._initialize_index()
        self.load()
    
    def _initialize_index(self):
        """Initialize FAISS index."""
        if FAISS_AVAILABLE:
            # Use FAISS index for fast similarity search
            self.index = faiss.IndexFlatIP(self.dimension)  # Inner product for cosine similarity
        else:
            print("Warning: FAISS not available. Using simple similarity search.")
            self.index = None
    
    def add_entity(self, entity: CodeEntity) -> None:
        """Add a code entity and generate its embedding."""
        # Add to base storage
        self._entities[entity.id] = entity
        
        # Generate embedding
        try:
            vector = self.embedding_generator.generate_embedding(entity)
            embedding = CodeEmbedding(
                entity_id=entity.id,
                vector=vector,
                metadata={"type": entity.type, "language": entity.language},
                created_at=datetime.now()
            )
            
            self.embeddings[entity.id] = embedding
            
            # Add to FAISS index
            if self.index is not None:
                # Normalize vector for cosine similarity
                normalized_vector = vector / np.linalg.norm(vector)
                self.index.add(normalized_vector.reshape(1, -1))
                
                # Track mapping
                index_id = self.index.ntotal - 1
                self.entity_id_to_index[entity.id] = index_id
                self.index_to_entity_id[index_id] = entity.id
                
        except Exception as e:
            print(f"Warning: Could not generate embedding for {entity.id}: {e}")
    
    def add_relationship(self, relationship: CodeRelationship) -> None:
        """Add a relationship between entities."""
        self._relationships[relationship.id] = relationship
    
    def get_entity(self, entity_id: str) -> Optional[CodeEntity]:
        """Retrieve an entity by ID."""
        return self._entities.get(entity_id)
    
    def search_entities(self, query: str, entity_type: Optional[str] = None, limit: int = 10) -> List[CodeEntity]:
        """Search for entities using semantic similarity."""
        if not query.strip():
            # If empty query but type specified, return entities of that type
            if entity_type:
                return [e for e in self._entities.values() if e.type == entity_type][:limit]
            return []
        
        try:
            # Generate query embedding
            query_vector = self._generate_query_embedding(query)
            
            if self.index is not None and self.index.ntotal > 0:
                # Use FAISS for fast search
                similarities, indices = self.index.search(query_vector.reshape(1, -1), min(limit * 2, self.index.ntotal))
                
                results = []
                for similarity, idx in zip(similarities[0], indices[0]):
                    if idx in self.index_to_entity_id:
                        entity_id = self.index_to_entity_id[idx]
                        entity = self._entities.get(entity_id)
                        
                        if entity and (not entity_type or entity.type == entity_type):
                            results.append(entity)
                            if len(results) >= limit:
                                break
                
                return results
            else:
                # Fallback: Manual similarity search
                return self._manual_similarity_search(query_vector, entity_type, limit)
                
        except Exception as e:
            print(f"Warning: Vector search failed, falling back to text search: {e}")
            # Fallback to text-based search
            return super().search_entities(query, entity_type)[:limit]
    
    def _generate_query_embedding(self, query: str) -> np.ndarray:
        """Generate embedding for a search query."""
        if self.embedding_generator.model is not None:
            embedding = self.embedding_generator.model.encode(query)
            normalized = embedding / np.linalg.norm(embedding)
            return normalized.astype(np.float32)
        else:
            # Fallback hash-based embedding
            embedding = self.embedding_generator._hash_based_embedding(query, self.dimension)
            return embedding / np.linalg.norm(embedding)
    
    def _manual_similarity_search(self, query_vector: np.ndarray, entity_type: Optional[str], limit: int) -> List[CodeEntity]:
        """Manual similarity search when FAISS is not available."""
        similarities = []
        
        for entity_id, embedding in self.embeddings.items():
            entity = self._entities.get(entity_id)
            if entity and (not entity_type or entity.type == entity_type):
                # Calculate cosine similarity
                entity_vector = embedding.vector / np.linalg.norm(embedding.vector)
                similarity = np.dot(query_vector, entity_vector)
                similarities.append((similarity, entity))
        
        # Sort by similarity and return top results
        similarities.sort(key=lambda x: x[0], reverse=True)
        return [entity for _, entity in similarities[:limit]]
    
    def find_similar_entities(self, entity_id: str, limit: int = 5) -> List[Tuple[CodeEntity, float]]:
        """Find entities similar to the given entity."""
        if entity_id not in self.embeddings:
            return []
        
        source_embedding = self.embeddings[entity_id]
        query_vector = source_embedding.vector / np.linalg.norm(source_embedding.vector)
        
        similarities = []
        for other_id, other_embedding in self.embeddings.items():
            if other_id != entity_id:
                other_vector = other_embedding.vector / np.linalg.norm(other_embedding.vector)
                similarity = np.dot(query_vector, other_vector)
                
                entity = self._entities.get(other_id)
                if entity:
                    similarities.append((entity, float(similarity)))
        
        # Sort by similarity and return top results
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:limit]
    
    def get_related_entities(self, entity_id: str, relationship_type: Optional[str] = None) -> List[Tuple[CodeEntity, CodeRelationship]]:
        """Get entities related to the given entity."""
        results = []
        
        for rel in self._relationships.values():
            if rel.source_id == entity_id or rel.target_id == entity_id:
                if relationship_type and rel.relationship_type != relationship_type:
                    continue
                
                # Get the related entity (not the source entity)
                related_id = rel.target_id if rel.source_id == entity_id else rel.source_id
                related_entity = self._entities.get(related_id)
                
                if related_entity:
                    results.append((related_entity, rel))
        
        return results
    
    def save(self) -> None:
        """Save the vector knowledge base to storage."""
        # Save entities (same as TextBasedKB)
        entities_data = {}
        for entity_id, entity in self._entities.items():
            entity_dict = entity.__dict__.copy()
            entity_dict['created_at'] = entity.created_at.isoformat()
            entities_data[entity_id] = entity_dict
        
        with open(self.entities_file, 'w', encoding='utf-8') as f:
            json.dump(entities_data, f, indent=2, ensure_ascii=False)
        
        # Save relationships
        relationships_data = {}
        for rel_id, rel in self._relationships.items():
            relationships_data[rel_id] = rel.__dict__
        
        relationships_file = self.storage_path / "relationships.json"
        with open(relationships_file, 'w', encoding='utf-8') as f:
            json.dump(relationships_data, f, indent=2, ensure_ascii=False)
        
        # Save embeddings
        with open(self.embeddings_file, 'wb') as f:
            pickle.dump({
                'embeddings': self.embeddings,
                'entity_id_to_index': self.entity_id_to_index,
                'index_to_entity_id': self.index_to_entity_id,
                'dimension': self.dimension
            }, f)
        
        # Save FAISS index
        if self.index is not None and self.index.ntotal > 0:
            faiss.write_index(self.index, str(self.index_file))
    
    def load(self) -> None:
        """Load the vector knowledge base from storage."""
        # Load entities
        if self.entities_file.exists():
            with open(self.entities_file, 'r', encoding='utf-8') as f:
                entities_data = json.load(f)
            
            for entity_id, entity_dict in entities_data.items():
                entity_dict['created_at'] = datetime.fromisoformat(entity_dict['created_at'])
                self._entities[entity_id] = CodeEntity(**entity_dict)
        
        # Load relationships
        relationships_file = self.storage_path / "relationships.json"
        if relationships_file.exists():
            with open(relationships_file, 'r', encoding='utf-8') as f:
                relationships_data = json.load(f)
            
            for rel_id, rel_dict in relationships_data.items():
                self._relationships[rel_id] = CodeRelationship(**rel_dict)
        
        # Load embeddings
        if self.embeddings_file.exists():
            with open(self.embeddings_file, 'rb') as f:
                data = pickle.load(f)
                self.embeddings = data['embeddings']
                self.entity_id_to_index = data['entity_id_to_index']
                self.index_to_entity_id = data['index_to_entity_id']
                if 'dimension' in data:
                    self.dimension = data['dimension']
        
        # Load FAISS index
        if self.index_file.exists() and FAISS_AVAILABLE:
            self.index = faiss.read_index(str(self.index_file))
        
    def clear(self) -> None:
        """Clear all data from the knowledge base."""
        self._entities.clear()
        self._relationships.clear()
        self.embeddings.clear()
        self.entity_id_to_index.clear()
        self.index_to_entity_id.clear()
        
        # Reset FAISS index
        self._initialize_index()
        
        # Remove files
        for file_path in [self.entities_file, self.embeddings_file, self.index_file]:
            if file_path.exists():
                file_path.unlink()
    
    def get_embedding_stats(self) -> Dict[str, Any]:
        """Get statistics about embeddings."""
        return {
            "total_embeddings": len(self.embeddings),
            "embedding_dimension": self.dimension,
            "embedding_model": self.embedding_model,
            "faiss_available": FAISS_AVAILABLE,
            "sentence_transformers_available": SENTENCE_TRANSFORMERS_AVAILABLE,
            "index_size": self.index.ntotal if self.index else 0
        }