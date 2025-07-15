# CodeFusion Workflow Diagrams

## 1. Repository Exploration and Indexing Workflow

```mermaid
sequenceDiagram
    participant U as User
    participant CLI as CLI Interface
    participant Config as Configuration
    participant Repo as Repository
    participant KB as Knowledge Base
    participant Indexer as Code Indexer
    participant Analyzer as Content Analyzer
    participant Storage as Storage Layer

    U->>CLI: 1. Start repository exploration
    CLI->>Config: 2. Load configuration
    Config-->>CLI: 3. Configuration ready
    
    CLI->>Repo: 4. Initialize repository access
    Repo-->>CLI: 5. Repository structure scanned
    
    CLI->>KB: 6. Initialize knowledge base
    KB->>Storage: 7. Connect to storage (Neo4j/Vector)
    Storage-->>KB: 8. Storage ready
    KB-->>CLI: 9. Knowledge base ready
    
    CLI->>Indexer: 10. Start indexing process
    
    loop For each file
        Indexer->>Repo: 11. Read file content
        Repo-->>Indexer: 12. File content
        
        Indexer->>Analyzer: 13. Analyze code structure
        Analyzer-->>Indexer: 14. Code entities extracted
        
        Indexer->>KB: 15. Store entities
        KB->>Storage: 16. Persist entities
        Storage-->>KB: 17. Entities stored
    end
    
    Indexer->>Analyzer: 18. Detect relationships
    Analyzer-->>Indexer: 19. Relationships found
    
    Indexer->>KB: 20. Store relationships
    KB->>Storage: 21. Persist relationships
    Storage-->>KB: 22. Relationships stored
    
    Indexer-->>CLI: 23. Indexing complete
    CLI-->>U: 24. Display results

    %% Professional color styling
    %%{init: {'theme':'base', 'themeVariables': {
        'primaryColor': '#4A90E2',
        'primaryTextColor': '#ffffff',
        'primaryBorderColor': '#357ABD',
        'lineColor': '#666666',
        'secondaryColor': '#E8F4FD',
        'tertiaryColor': '#F8FBFF',
        'background': '#ffffff',
        'mainBkg': '#4A90E2',
        'secondBkg': '#7FB069',
        'tertiaryBkg': '#E67E22',
        'actor0': '#4A90E2',
        'actor1': '#7FB069',
        'actor2': '#E67E22',
        'actor3': '#9B59B6',
        'actor4': '#34495E',
        'actor5': '#E74C3C',
        'actor6': '#F39C12',
        'actor7': '#16A085',
        'actorTextColor': '#ffffff',
        'actorLineColor': '#666666',
        'signalColor': '#FFFFFF',
        'signalTextColor': '#FFFFFF',
        'messageFontSize': '18px',
        'noteFontSize': '18px',
        'actorFontSize': '20px',
        'c0': '#E8F4FD',
        'c1': '#E8F6E8',
        'c2': '#FDF2E8',
        'c3': '#F3E8F6',
        'c4': '#E8EDF3',
        'c5': '#FDEBEB',
        'c6': '#FDF6E8',
        'c7': '#E8F6F3'
    }}}%%
```

## 2. Query Processing Workflow

```mermaid
sequenceDiagram
    participant U as User
    participant CLI as CLI Interface
    participant Config as Configuration
    participant KB as Knowledge Base
    participant LLM as LLM Service
    participant Agent as Reasoning Agent
    participant Storage as Storage Layer

    U->>CLI: 1. Submit query
    CLI->>Config: 2. Load configuration
    Config-->>CLI: 3. Configuration ready
    
    CLI->>KB: 4. Initialize knowledge base
    KB->>Storage: 5. Connect to storage
    Storage-->>KB: 6. Storage ready
    
    CLI->>LLM: 7. Initialize LLM service
    LLM-->>CLI: 8. LLM ready
    
    CLI->>Agent: 9. Create reasoning agent
    Agent-->>CLI: 10. Agent ready
    
    CLI->>Agent: 11. Process query
    Agent->>Agent: 12. Analyze query
    
    alt Vector Search
        Agent->>KB: 13a. Semantic search
        KB->>Storage: 14a. Query vectors
        Storage-->>KB: 15a. Similar entities
        KB-->>Agent: 16a. Search results
    else Graph Search
        Agent->>KB: 13b. Graph traversal
        KB->>Storage: 14b. Query graph
        Storage-->>KB: 15b. Related entities
        KB-->>Agent: 16b. Graph results
    end
    
    Agent->>KB: 17. Get entity context
    KB->>Storage: 18. Retrieve relationships
    Storage-->>KB: 19. Context data
    KB-->>Agent: 20. Rich context
    
    Agent->>LLM: 21. Generate response
    LLM-->>Agent: 22. Response generated
    
    Agent->>Agent: 23. Post-process answer
    Agent-->>CLI: 24. Final answer
    CLI-->>U: 25. Display response

    %% Professional color styling
    %%{init: {'theme':'base', 'themeVariables': {
        'primaryColor': '#4A90E2',
        'primaryTextColor': '#ffffff',
        'primaryBorderColor': '#357ABD',
        'lineColor': '#666666',
        'secondaryColor': '#E8F4FD',
        'tertiaryColor': '#F8FBFF',
        'background': '#ffffff',
        'mainBkg': '#4A90E2',
        'secondBkg': '#7FB069',
        'tertiaryBkg': '#E67E22',
        'actor0': '#4A90E2',
        'actor1': '#7FB069',
        'actor2': '#E67E22',
        'actor3': '#9B59B6',
        'actor4': '#34495E',
        'actor5': '#E74C3C',
        'actor6': '#F39C12',
        'actor7': '#16A085',
        'actorTextColor': '#ffffff',
        'actorLineColor': '#666666',
        'signalColor': '#FFFFFF',
        'signalTextColor': '#FFFFFF',
        'messageFontSize': '18px',
        'noteFontSize': '18px',
        'actorFontSize': '20px',
        'c0': '#E8F4FD',
        'c1': '#E8F6E8',
        'c2': '#FDF2E8',
        'c3': '#F3E8F6',
        'c4': '#E8EDF3',
        'c5': '#FDEBEB',
        'c6': '#FDF6E8',
        'c7': '#E8F6F3'
    }}}%%
```

## Key Components Interaction Summary

### Exploration Workflow Key Points:
1. **Configuration Loading**: System loads user settings and preferences
2. **Repository Access**: Scans and analyzes repository structure
3. **Knowledge Base Setup**: Initializes storage layer (Neo4j or Vector DB)
4. **Content Analysis**: Extracts code entities and relationships
5. **Persistent Storage**: Saves structured knowledge for future queries

### Query Workflow Key Points:
1. **Query Analysis**: Processes natural language questions
2. **Multi-Strategy Search**: Uses vector similarity and graph traversal
3. **Context Enrichment**: Gathers related entities and relationships
4. **LLM Integration**: Generates comprehensive answers with context
5. **Response Delivery**: Returns structured answers with supporting evidence

Both workflows support dual storage backends (Neo4j for graph analytics, Vector DB for semantic search) with automatic fallback capabilities.