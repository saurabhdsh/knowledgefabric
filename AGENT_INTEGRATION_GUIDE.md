# 🤖 Knowledge Fabric Agent Integration Guide

## 🎯 **Overview**

This guide provides comprehensive examples for integrating Knowledge Fabric with various agent frameworks and programming languages. Perfect for developers building AI agents that need access to structured knowledge bases.

## 🚀 **Quick Start**

### **Base URL**: `http://localhost:8000`
### **Fabric ID**: Each knowledge fabric has a unique ID (e.g., `fabric_43d91a747d784bd78a3cfd8046dc4870_pdf_1753188218`)

---

## 📋 **Available Endpoints**

### **1. Query Knowledge Fabric**
```http
POST /api/v1/knowledge/query/{fabric_id}
```

**Request:**
```json
{
  "query": "What are the claims procedures?",
  "llm_provider": "openai"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Knowledge base query completed",
  "data": {
    "fabric_id": "fabric_43d91a747d784bd78a3cfd8046dc4870_pdf_1753188218",
    "fabric_name": "Claims_Processing_Guide",
    "query": "What are the claims procedures?",
    "answer": "Based on the document content...",
    "confidence": 0.85,
    "model_status": "trained",
    "relevant_chunks_found": 3,
    "llm_provider": "openai",
    "processing_time": "2.1s"
  }
}
```

### **2. Validate Knowledge Base**
```http
POST /api/v1/knowledge/validate-knowledge/{fabric_id}
```

**Request:**
```json
{
  "questions": [
    "What is this document about?",
    "What are the key procedures?"
  ]
}
```

### **3. Get API Key Status**
```http
GET /api/v1/knowledge/api-keys/status
```

---

## 🐍 **LangChain Integration**

### **Basic LangChain Tool**

```python
from langchain.agents import Tool
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
import requests

class KnowledgeFabricTool:
    def __init__(self, fabric_id, base_url="http://localhost:8000"):
        self.fabric_id = fabric_id
        self.base_url = base_url
    
    def query_knowledge(self, query: str) -> str:
        """Query the knowledge fabric for information"""
        url = f"{self.base_url}/api/v1/knowledge/query/{self.fabric_id}"
        response = requests.post(url, json={"query": query})
        data = response.json()
        
        if data.get("success"):
            return data["data"]["answer"]
        else:
            return f"Error: {data.get('message', 'Unknown error')}"

# Initialize the tool
knowledge_tool = KnowledgeFabricTool("your_fabric_id")

# Create LangChain tool
tool = Tool(
    name="knowledge_fabric",
    description="Query the knowledge fabric for specific information about documents and processes",
    func=knowledge_tool.query_knowledge
)

# Create agent
llm = ChatOpenAI(temperature=0)
agent = create_openai_functions_agent(llm, [tool], prompt)
agent_executor = AgentExecutor(agent=agent, tools=[tool], verbose=True)

# Use the agent
result = agent_executor.invoke({
    "input": "What are the key stakeholders mentioned in the knowledge fabric?"
})
```

### **Advanced LangChain Integration**

```python
from langchain.agents import Tool
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
import requests
import json

class EnhancedKnowledgeFabricTool:
    def __init__(self, fabric_id, base_url="http://localhost:8000"):
        self.fabric_id = fabric_id
        self.base_url = base_url
    
    def query_knowledge(self, query: str) -> str:
        """Query the knowledge fabric with detailed response"""
        url = f"{self.base_url}/api/v1/knowledge/query/{self.fabric_id}"
        response = requests.post(url, json={
            "query": query,
            "llm_provider": "openai"
        })
        data = response.json()
        
        if data.get("success"):
            result = data["data"]
            return f"""Answer: {result['answer']}
Confidence: {result['confidence']}
Processing Time: {result['processing_time']}
Relevant Chunks: {result['relevant_chunks_found']}"""
        else:
            return f"Error: {data.get('message', 'Unknown error')}"
    
    def validate_knowledge(self, questions: list) -> str:
        """Validate the knowledge base with custom questions"""
        url = f"{self.base_url}/api/v1/knowledge/validate-knowledge/{self.fabric_id}"
        response = requests.post(url, json={"questions": questions})
        data = response.json()
        
        if data.get("success"):
            result = data["data"]
            return f"""Validation Score: {result['validation_score']}
Assessment: {result['overall_assessment']}
Questions Tested: {result['test_questions']}"""
        else:
            return f"Error: {data.get('message', 'Unknown error')}"

# Initialize enhanced tool
enhanced_tool = EnhancedKnowledgeFabricTool("your_fabric_id")

# Create multiple tools
query_tool = Tool(
    name="query_knowledge_fabric",
    description="Query the knowledge fabric for specific information",
    func=enhanced_tool.query_knowledge
)

validate_tool = Tool(
    name="validate_knowledge_fabric",
    description="Validate the knowledge base with custom questions",
    func=enhanced_tool.validate_knowledge
)

# Create agent with custom prompt
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an AI assistant that helps users query and validate knowledge fabrics. Use the available tools to provide accurate information."),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

llm = ChatOpenAI(temperature=0)
agent = create_openai_functions_agent(llm, [query_tool, validate_tool], prompt)
agent_executor = AgentExecutor(agent=agent, tools=[query_tool, validate_tool], verbose=True)

# Example usage
result = agent_executor.invoke({
    "input": "What are the claims procedures and validate if the knowledge base understands this topic?",
    "chat_history": []
})
```

---

## 🐍 **Python Client Examples**

### **Basic Python Client**

```python
import requests
import json

class KnowledgeFabricClient:
    def __init__(self, fabric_id, base_url="http://localhost:8000"):
        self.fabric_id = fabric_id
        self.base_url = base_url
    
    def query(self, question: str) -> dict:
        """Query the knowledge fabric"""
        url = f"{self.base_url}/api/v1/knowledge/query/{self.fabric_id}"
        response = requests.post(url, json={"query": question})
        return response.json()
    
    def validate(self, questions: list) -> dict:
        """Validate the knowledge base"""
        url = f"{self.base_url}/api/v1/knowledge/validate-knowledge/{self.fabric_id}"
        response = requests.post(url, json={"questions": questions})
        return response.json()

# Usage
client = KnowledgeFabricClient("your_fabric_id")

# Query the knowledge fabric
result = client.query("What are the key stakeholders?")
print(f"Answer: {result['data']['answer']}")
print(f"Confidence: {result['data']['confidence']}")
```

### **Advanced Python Client**

```python
import requests
import json
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class QueryResult:
    answer: str
    confidence: float
    processing_time: str
    relevant_chunks: int
    fabric_name: str

class AdvancedKnowledgeFabricClient:
    def __init__(self, fabric_id: str, base_url: str = "http://localhost:8000"):
        self.fabric_id = fabric_id
        self.base_url = base_url
    
    def query(self, question: str, llm_provider: str = "openai") -> QueryResult:
        """Query the knowledge fabric with detailed response"""
        url = f"{self.base_url}/api/v1/knowledge/query/{self.fabric_id}"
        response = requests.post(url, json={
            "query": question,
            "llm_provider": llm_provider
        })
        data = response.json()
        
        if data.get("success"):
            result_data = data["data"]
            return QueryResult(
                answer=result_data["answer"],
                confidence=result_data["confidence"],
                processing_time=result_data["processing_time"],
                relevant_chunks=result_data["relevant_chunks_found"],
                fabric_name=result_data["fabric_name"]
            )
        else:
            raise Exception(f"Query failed: {data.get('message', 'Unknown error')}")
    
    def validate_knowledge(self, questions: List[str]) -> Dict:
        """Validate the knowledge base"""
        url = f"{self.base_url}/api/v1/knowledge/validate-knowledge/{self.fabric_id}"
        response = requests.post(url, json={"questions": questions})
        return response.json()
    
    def get_status(self) -> Dict:
        """Get fabric status"""
        url = f"{self.base_url}/api/v1/knowledge/"
        response = requests.get(url)
        return response.json()

# Usage example
client = AdvancedKnowledgeFabricClient("your_fabric_id")

try:
    # Query with specific LLM provider
    result = client.query("What are the claims procedures?", llm_provider="openai")
    print(f"Answer: {result.answer}")
    print(f"Confidence: {result.confidence}")
    print(f"Processing Time: {result.processing_time}")
    
    # Validate knowledge base
    validation = client.validate_knowledge([
        "What is this document about?",
        "What are the key procedures?"
    ])
    print(f"Validation Score: {validation['data']['validation_score']}")
    
except Exception as e:
    print(f"Error: {e}")
```

---

## 🟨 **JavaScript Client Examples**

### **Basic JavaScript Client**

```javascript
class KnowledgeFabricClient {
    constructor(fabricId, baseUrl = 'http://localhost:8000') {
        this.fabricId = fabricId;
        this.baseUrl = baseUrl;
    }
    
    async query(question) {
        const url = `${this.baseUrl}/api/v1/knowledge/query/${this.fabricId}`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query: question })
        });
        return await response.json();
    }
    
    async validate(questions) {
        const url = `${this.baseUrl}/api/v1/knowledge/validate-knowledge/${this.fabricId}`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ questions })
        });
        return await response.json();
    }
}

// Usage
const client = new KnowledgeFabricClient('your_fabric_id');

// Query the knowledge fabric
client.query('What are the key stakeholders?')
    .then(result => {
        console.log('Answer:', result.data.answer);
        console.log('Confidence:', result.data.confidence);
    })
    .catch(error => console.error('Error:', error));
```

### **Advanced JavaScript Client**

```javascript
class AdvancedKnowledgeFabricClient {
    constructor(fabricId, baseUrl = 'http://localhost:8000') {
        this.fabricId = fabricId;
        this.baseUrl = baseUrl;
    }
    
    async query(question, llmProvider = 'openai') {
        const url = `${this.baseUrl}/api/v1/knowledge/query/${this.fabricId}`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                query: question,
                llm_provider: llmProvider 
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            return {
                answer: data.data.answer,
                confidence: data.data.confidence,
                processingTime: data.data.processing_time,
                relevantChunks: data.data.relevant_chunks_found,
                fabricName: data.data.fabric_name
            };
        } else {
            throw new Error(data.message || 'Query failed');
        }
    }
    
    async validateKnowledge(questions) {
        const url = `${this.baseUrl}/api/v1/knowledge/validate-knowledge/${this.fabricId}`;
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ questions })
        });
        return await response.json();
    }
    
    async getStatus() {
        const url = `${this.baseUrl}/api/v1/knowledge/`;
        const response = await fetch(url);
        return await response.json();
    }
}

// Usage with async/await
async function example() {
    const client = new AdvancedKnowledgeFabricClient('your_fabric_id');
    
    try {
        // Query with specific LLM provider
        const result = await client.query('What are the claims procedures?', 'openai');
        console.log('Answer:', result.answer);
        console.log('Confidence:', result.confidence);
        console.log('Processing Time:', result.processingTime);
        
        // Validate knowledge base
        const validation = await client.validateKnowledge([
            'What is this document about?',
            'What are the key procedures?'
        ]);
        console.log('Validation Score:', validation.data.validation_score);
        
    } catch (error) {
        console.error('Error:', error);
    }
}

// Run the example
example();
```

---

## 🔧 **Agent Framework Integration Examples**

### **OpenAI Functions Agent**

```python
from openai import OpenAI
import requests

class KnowledgeFabricFunctions:
    def __init__(self, fabric_id, base_url="http://localhost:8000"):
        self.fabric_id = fabric_id
        self.base_url = base_url
    
    def query_knowledge(self, query: str) -> str:
        """Query the knowledge fabric for information"""
        url = f"{self.base_url}/api/v1/knowledge/query/{self.fabric_id}"
        response = requests.post(url, json={"query": query})
        data = response.json()
        
        if data.get("success"):
            return data["data"]["answer"]
        else:
            return f"Error: {data.get('message', 'Unknown error')}"

# Initialize OpenAI client
client = OpenAI()

# Define functions
functions = [
    {
        "type": "function",
        "function": {
            "name": "query_knowledge_fabric",
            "description": "Query the knowledge fabric for specific information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The question to ask about the knowledge fabric"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# Initialize knowledge fabric
knowledge_fabric = KnowledgeFabricFunctions("your_fabric_id")

# Use in conversation
messages = [
    {"role": "user", "content": "What are the claims procedures mentioned in the knowledge fabric?"}
]

response = client.chat.completions.create(
    model="gpt-4",
    messages=messages,
    functions=functions,
    function_call="auto"
)

# Handle function call
if response.choices[0].message.function_call:
    function_name = response.choices[0].message.function_call.name
    function_args = json.loads(response.choices[0].message.function_call.arguments)
    
    if function_name == "query_knowledge_fabric":
        result = knowledge_fabric.query_knowledge(function_args["query"])
        messages.append({
            "role": "function",
            "name": function_name,
            "content": result
        })
```

### **AutoGen Agent Integration**

```python
import autogen
import requests

class KnowledgeFabricAgent:
    def __init__(self, fabric_id, base_url="http://localhost:8000"):
        self.fabric_id = fabric_id
        self.base_url = base_url
    
    def query_knowledge(self, query: str) -> str:
        """Query the knowledge fabric"""
        url = f"{self.base_url}/api/v1/knowledge/query/{self.fabric_id}"
        response = requests.post(url, json={"query": query})
        data = response.json()
        
        if data.get("success"):
            return data["data"]["answer"]
        else:
            return f"Error: {data.get('message', 'Unknown error')}"

# Initialize knowledge fabric
knowledge_fabric = KnowledgeFabricAgent("your_fabric_id")

# Create AutoGen agents
config_list = [
    {
        'model': 'gpt-4',
        'api_key': 'your-openai-api-key'
    }
]

# Create the assistant agent
assistant = autogen.AssistantAgent(
    name="assistant",
    system_message="You are a helpful assistant that can query knowledge fabrics. When you need information from the knowledge fabric, use the query_knowledge function.",
    llm_config={"config_list": config_list}
)

# Create the user proxy agent
user_proxy = autogen.UserProxyAgent(
    name="user_proxy",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=10,
    is_termination_msg=lambda x: x.get("content", "").rstrip().endswith("TERMINATE"),
    code_execution_config={"work_dir": "workspace"},
    llm_config={"config_list": config_list}
)

# Add knowledge fabric function to user proxy
def query_knowledge_fabric(query: str) -> str:
    return knowledge_fabric.query_knowledge(query)

user_proxy.register_function(
    function_map={
        "query_knowledge_fabric": query_knowledge_fabric
    }
)

# Start conversation
user_proxy.initiate_chat(
    assistant,
    message="What are the key stakeholders mentioned in the knowledge fabric?"
)
```

---

## 🚀 **Best Practices**

### **1. Error Handling**
```python
try:
    result = client.query("What are the procedures?")
    if result.get("success"):
        print(f"Answer: {result['data']['answer']}")
    else:
        print(f"Error: {result.get('message')}")
except Exception as e:
    print(f"Request failed: {e}")
```

### **2. Rate Limiting**
```python
import time

def query_with_rate_limit(client, query, delay=1.0):
    result = client.query(query)
    time.sleep(delay)  # Rate limiting
    return result
```

### **3. Retry Logic**
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session_with_retry():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session
```

### **4. Authentication (Production)**
```python
class AuthenticatedKnowledgeFabricClient:
    def __init__(self, fabric_id, api_key, base_url="https://your-domain.com"):
        self.fabric_id = fabric_id
        self.api_key = api_key
        self.base_url = base_url
    
    def query(self, question: str) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}/api/v1/knowledge/query/{self.fabric_id}"
        response = requests.post(url, json={"query": question}, headers=headers)
        return response.json()
```

---

## 📊 **Response Format Reference**

### **Successful Query Response**
```json
{
  "success": true,
  "message": "Knowledge base query completed",
  "data": {
    "fabric_id": "fabric_43d91a747d784bd78a3cfd8046dc4870_pdf_1753188218",
    "fabric_name": "Claims_Processing_Guide",
    "query": "What are the claims procedures?",
    "answer": "Based on the document content...",
    "confidence": 0.85,
    "model_status": "trained",
    "relevant_chunks_found": 3,
    "llm_provider": "openai",
    "processing_time": "2.1s"
  }
}
```

### **Error Response**
```json
{
  "success": false,
  "message": "Error message here",
  "error_code": "ERROR_CODE"
}
```

---

## 🎯 **Use Cases**

### **1. Customer Support Agent**
```python
# Agent that can answer questions about company policies
def handle_customer_inquiry(question: str) -> str:
    result = knowledge_fabric.query(question)
    return result["data"]["answer"]
```

### **2. Document Analysis Agent**
```python
# Agent that analyzes documents and provides insights
def analyze_document_questions(questions: list) -> dict:
    return knowledge_fabric.validate(questions)
```

### **3. Research Assistant**
```python
# Agent that helps with research by querying knowledge bases
def research_topic(topic: str) -> str:
    result = knowledge_fabric.query(f"What information is available about {topic}?")
    return result["data"]["answer"]
```

---

## 🔗 **Integration Checklist**

- [ ] **Get Fabric ID**: Obtain the unique fabric ID from the Knowledge Fabric interface
- [ ] **Test Connection**: Verify the API endpoints are accessible
- [ ] **Implement Error Handling**: Add proper error handling for failed requests
- [ ] **Add Rate Limiting**: Implement delays between requests to avoid overwhelming the API
- [ ] **Test with Sample Queries**: Verify the integration works with your specific use case
- [ ] **Add Authentication**: For production, implement proper authentication
- [ ] **Monitor Performance**: Track response times and success rates
- [ ] **Handle Edge Cases**: Plan for scenarios like empty responses or high confidence scores

---

## 📞 **Support**

For questions about agent integration:
1. Check the API documentation in the "Use Fabric" dialog
2. Test endpoints using the provided examples
3. Review error messages for troubleshooting
4. Contact support if issues persist

**Happy Agent Building! 🤖✨** 