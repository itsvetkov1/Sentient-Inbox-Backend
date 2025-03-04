# System Patterns

## Architecture Overview

### Core Components
1. Email Processing Pipeline
   - GmailClient (gmail.py)
   - EmailProcessor (email_processor.py)
   - ContentPreprocessor (content.py)
   - EmailDateService (content.py)
   - LlamaAnalyzer (llama_analyzer.py)
   - DeepseekAnalyzer (deepseek_analyzer.py)
   - ResponseGenerator (email_writer.py)

2. Content Processing System
   - HTML Cleaning (BeautifulSoup)
   - Date Pattern Recognition
   - Token Management
   - Pattern Preservation

3. Data Management
   - SecureStorage (secure_storage.py)
   - WeeklyRollingHistory
   - StructuredDataStorage
   - BackupManager

## Design Patterns

### Data Class Pattern
- ProcessedContent for structured content results
- AnalysisResult for model outputs
- Type-safe access to analysis components
- Comprehensive metadata tracking

### Service Pattern
- EmailDateService for date handling
- ContentPreprocessor for content management
- DateProcessor for pattern recognition
- ContentChunker for token management

### Strategy Pattern
- Implemented in content preprocessing
- Flexible date parsing strategies
- Configurable pattern preservation
- Token limit enforcement strategies

### Chain of Responsibility
- Content preprocessing pipeline
- Three-stage analysis system
- Pattern preservation chain
- Error handling chain

## Component Relationships

### Content Processing Flow
```
Raw Email Content
    ↓
HTML Cleaning (BeautifulSoup)
    ↓
Date Extraction (RFC 2822/ISO 8601)
    ↓
Pattern Recognition & Preservation
    ↓
Token Management & Chunking
    ↓
Processed Content
```

### Analysis Flow
```
Unread Email
    ↓
Content Preprocessing
    - HTML Cleaning
    - Date Extraction
    - Pattern Preservation
    - Token Management
    ↓
Stage 1: Initial Classification (LlamaAnalyzer)
    - Content Chunking
    - Classification Prompt
    - Response Parsing
    ↓
Meeting-related? → Yes → Stage 2: Detailed Analysis (DeepseekAnalyzer)
    ↓
Stage 3: Final Decision (LlamaAnalyzer)
    - Decision Prompt
    - Response Validation
    - Metadata Collection
    ↓
Categorization (standard_response, needs_review, ignored)
    ↓
Processing Decision
```

## Technical Decisions

### Content Processing
- BeautifulSoup for robust HTML cleaning
- RFC 2822 and ISO 8601 date parsing
- Paragraph-based content chunking
- Pattern-aware token management

### Error Handling
- Custom ContentProcessingError
- Comprehensive error recovery
- Detailed processing statistics
- Pattern preservation validation

### Performance Optimization
- Efficient HTML parsing
- Smart content chunking
- Pattern-based preservation
- Token estimation optimization

### Security
- HTML content sanitization
- Pattern validation security
- Error message safety
- Processing metadata privacy

## Implementation Patterns

### Content Preprocessing
```python
@dataclass
class ProcessedContent:
    content: str
    metadata: Dict[str, any]
    token_estimate: int
    processing_stats: Dict[str, any]
    extracted_dates: Set[str] = None

class ContentPreprocessor:
    def preprocess_content(self, content: str) -> ProcessedContent:
        # Clean HTML → Extract Dates → Preserve Patterns → Manage Tokens
        cleaned = self._clean_html(content)
        dates = DateProcessor.extract_dates(cleaned)
        preserved = self._extract_key_information(cleaned)
        final = self._enforce_token_limit(preserved)
        return ProcessedContent(...)
```

### Date Processing
```python
class EmailDateService:
    @staticmethod
    def parse_email_date(date_str: str) -> Tuple[datetime, bool]:
        # Try RFC 2822 → ISO 8601 → Additional Formats
        try:
            email_tuple = email.utils.parsedate_tz(date_str)
            if email_tuple:
                return datetime.fromtimestamp(
                    email.utils.mktime_tz(email_tuple),
                    ZoneInfo("UTC")
                ), True
        except:
            # Fallback strategies...
            pass
```

### Content Chunking
```python
class ContentChunker:
    def chunk_content(self, content: str) -> List[str]:
        # Split content while preserving context
        if len(content.split()) <= self.max_tokens:
            return [content]
            
        chunks = []
        for paragraph in content.split('\n\n'):
            # Intelligent chunking with pattern preservation
            if self._should_preserve(paragraph):
                chunks.append(paragraph)
```

### Pattern Preservation
```python
def _extract_key_information(self, content: str) -> str:
    # Keep content manageable while preserving patterns
    paragraphs = content.split('\n\n')
    selected = [paragraphs[0]]  # Keep first
    
    # Preserve important patterns
    for paragraph in paragraphs[1:-1]:
        if any(re.search(pattern, paragraph, re.IGNORECASE) 
              for pattern in self.preserve_patterns):
            selected.append(paragraph)
            
    if len(selected) < self.max_paragraphs:
        selected.append(paragraphs[-1])  # Keep last
        
    return '\n\n'.join(selected)
```

This architecture ensures reliable and efficient email content processing through sophisticated preprocessing, robust error handling, and intelligent pattern preservation.
