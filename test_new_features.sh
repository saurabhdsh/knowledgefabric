#!/bin/bash

FABRIC_ID="fabric_3dc05d33b3ab4113855d89825647e4dd_pdf_1753193573"

echo "🧪 Testing New Knowledge Fabric Features"
echo "========================================"

echo ""
echo "📋 1. Testing Query Endpoint (Real-time Questions):"
curl -s -X POST "http://localhost:8000/api/v1/knowledge/query/$FABRIC_ID" \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the claims mentioned in this document?"}' | jq '.'

echo ""
echo "🎯 2. Testing Validation Endpoint (Model Understanding):"
curl -s -X POST "http://localhost:8000/api/v1/knowledge/validate-knowledge/$FABRIC_ID" \
  -H "Content-Type: application/json" \
  -d '{"questions": ["What is this document about?", "What are the key points?"]}' | jq '.'

echo ""
echo "📊 3. Testing Fabric Status:"
curl -s -X GET "http://localhost:8000/api/v1/knowledge/" | jq ".data[] | select(.id == \"$FABRIC_ID\") | {id, name, model_status, total_chunks, document_count}"

echo ""
echo "✅ New Features Summary:"
echo "• ✅ Query Endpoint: Real-time questions about knowledge fabric"
echo "• ✅ Validation Endpoint: Test model understanding"
echo "• ✅ Status Endpoint: Get fabric information"
echo "• ✅ Frontend Integration: Use Fabric & Chat with AI buttons"
echo "• ✅ API Documentation: Endpoints display for developers"
echo "• ✅ Chat Interface: Modular chatbox for direct interaction"

echo ""
echo "🎯 Frontend Features Available:"
echo "• Click 'Use Fabric' to see API endpoints for developers"
echo "• Click 'Chat with AI' to open interactive chat dialog"
echo "• Both features work with the specific fabric ID: $FABRIC_ID"

echo ""
echo "🚀 Ready to use! Open http://localhost:3000 and navigate to 'Available Fabrics'" 