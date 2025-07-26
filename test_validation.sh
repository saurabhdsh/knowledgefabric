#!/bin/bash

echo "🔍 Knowledge Fabric Validation Test"
echo "=================================="

# Get the list of fabrics
echo "📋 Available Knowledge Fabrics:"
curl -s -X GET http://localhost:8000/api/v1/knowledge/ -H "Content-Type: application/json" | jq '.data[] | {id, name, model_status, last_training}'

echo ""
echo "🧪 Testing Knowledge Validation..."

# Get the first trained fabric ID
FABRIC_ID=$(curl -s -X GET http://localhost:8000/api/v1/knowledge/ -H "Content-Type: application/json" | jq -r '.data[] | select(.model_status == "trained") | .id' | head -1)

if [ "$FABRIC_ID" != "null" ] && [ -n "$FABRIC_ID" ]; then
    echo "✅ Found trained fabric: $FABRIC_ID"
    echo ""
    echo "🔬 Running validation test..."
    
    # Test validation
    curl -s -X POST "http://localhost:8000/api/v1/knowledge/validate-knowledge/$FABRIC_ID" \
        -H "Content-Type: application/json" \
        -d '{
            "questions": [
                "What is this document about?",
                "What are the key points discussed?",
                "What is the main purpose of this document?"
            ]
        }' | jq '.'
else
    echo "❌ No trained fabrics found. Please create a knowledge fabric first."
fi

echo ""
echo "🎯 To test with a specific fabric ID, use:"
echo "curl -X POST http://localhost:8000/api/v1/knowledge/validate-knowledge/YOUR_FABRIC_ID \\"
echo "  -H \"Content-Type: application/json\" \\"
echo "  -d '{\"questions\": [\"Your question here?\"]}'" 