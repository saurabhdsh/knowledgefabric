#!/bin/bash

FABRIC_ID="fabric_43d91a747d784bd78a3cfd8046dc4870_pdf_1753188218"

echo "🧪 Testing Knowledge Fabric: $FABRIC_ID"
echo "=========================================="

echo ""
echo "📋 1. Checking Fabric Status:"
curl -s -X GET http://localhost:8000/api/v1/knowledge/ -H "Content-Type: application/json" | jq ".data[] | select(.id == \"$FABRIC_ID\") | {id, name, model_status, last_training}"

echo ""
echo "🔍 2. Testing Knowledge Validation:"
curl -s -X POST "http://localhost:8000/api/v1/knowledge/validate-knowledge/$FABRIC_ID" \
  -H "Content-Type: application/json" \
  -d '{"questions": ["What is this document about?", "What are the key points?"]}' | jq '.'

echo ""
echo "❓ 3. Testing Claims Query:"
curl -s -X POST "http://localhost:8000/api/v1/knowledge/query/$FABRIC_ID" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the claims mentioned in this document?"}' | jq '.'

echo ""
echo "🎯 4. Testing Purpose Query:"
curl -s -X POST "http://localhost:8000/api/v1/knowledge/query/$FABRIC_ID" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the purpose of this document?"}' | jq '.'

echo ""
echo "📝 5. Testing General Query:"
curl -s -X POST "http://localhost:8000/api/v1/knowledge/query/$FABRIC_ID" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this document about?"}' | jq '.'

echo ""
echo "✅ Testing Complete!"
echo ""
echo "🎯 To test with custom questions, use:"
echo "curl -X POST http://localhost:8000/api/v1/knowledge/query/$FABRIC_ID \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"query\": \"Your question here?\"}'" 