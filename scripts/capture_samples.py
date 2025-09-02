#!/usr/bin/env python3
"""Capture API sample responses for testing and documentation."""

import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class APITester:
    """API testing and sample capture utility."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = requests.Session()
        self.samples_dir = Path("docs/samples")
        self.samples_dir.mkdir(parents=True, exist_ok=True)
        self.results = {}
        
    def save_json(self, filename: str, data: Any) -> None:
        """Save data as pretty JSON."""
        filepath = self.samples_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"  💾 Saved {filepath}")
        
    def save_text(self, filename: str, content: str) -> None:
        """Save text content."""
        filepath = self.samples_dir / filename
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  💾 Saved {filepath}")
        
    def save_binary(self, filename: str, content: bytes) -> None:
        """Save binary content."""
        filepath = self.samples_dir / filename
        with open(filepath, 'wb') as f:
            f.write(content)
        print(f"  💾 Saved {filepath}")
        
    def test_healthz(self) -> bool:
        """Test health check endpoint."""
        print("🏥 Testing GET /healthz")
        try:
            response = self.session.get(f"{self.base_url}/healthz")
            response.raise_for_status()
            
            data = response.json()
            self.save_json("healthz.json", data)
            
            # Validate response structure
            success = "ok" in data and data["ok"] is True
            self.results["healthz"] = {"success": success, "status": response.status_code}
            
            if success:
                print("  ✅ Health check passed")
            else:
                print("  ❌ Health check failed - missing 'ok: true'")
                
            return success
            
        except Exception as e:
            print(f"  ❌ Health check failed: {e}")
            self.results["healthz"] = {"success": False, "error": str(e)}
            return False
            
    def test_create_quote(self) -> Optional[int]:
        """Test quote creation endpoint."""
        print("📋 Testing POST /actions/create_quote")
        try:
            payload = {
                "account_id": 1,  # Acme Ltd from seed data
                "pricebook_id": 1,  # Standard USD pricebook
                "lines": [
                    {"sku_id": 7, "qty": 10},  # Widget - Standard
                    {"sku_id": 8, "qty": 10, "discount_pct": 0.10}  # VPN License with 10% discount
                ],
                "idempotency_key": f"test-{int(time.time())}"
            }
            
            response = self.session.post(
                f"{self.base_url}/actions/create_quote",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            data = response.json()
            self.save_json("create_quote.json", {
                "request": payload,
                "response": data,
                "status_code": response.status_code
            })
            
            # Validate response structure
            success = "quote_id" in data and isinstance(data["quote_id"], int)
            quote_id = data.get("quote_id") if success else None
            
            self.results["create_quote"] = {
                "success": success, 
                "status": response.status_code,
                "quote_id": quote_id
            }
            
            if success:
                print(f"  ✅ Quote created successfully (ID: {quote_id})")
            else:
                print("  ❌ Quote creation failed - missing quote_id")
                
            return quote_id
            
        except Exception as e:
            print(f"  ❌ Quote creation failed: {e}")
            self.results["create_quote"] = {"success": False, "error": str(e)}
            return None
            
    def test_get_quote(self, quote_id: int) -> bool:
        """Test get quote endpoint."""
        print(f"📋 Testing GET /quotes/{quote_id}")
        try:
            response = self.session.get(f"{self.base_url}/quotes/{quote_id}")
            response.raise_for_status()
            
            data = response.json()
            self.save_json(f"quote_{quote_id}.json", data)
            
            # Validate response structure
            required_fields = ["quote_id", "account_id", "pricebook_id", "status", "lines", "total_amount"]
            success = all(field in data for field in required_fields)
            
            if success:
                # Additional validation for lines structure
                lines_valid = all(
                    isinstance(line, dict) and "sku_id" in line and "qty" in line
                    for line in data.get("lines", [])
                )
                success = success and lines_valid
            
            self.results["get_quote"] = {
                "success": success, 
                "status": response.status_code,
                "quote_id": quote_id
            }
            
            if success:
                print(f"  ✅ Quote retrieved successfully (Total: ${data.get('total_amount', 0):.2f})")
            else:
                print("  ❌ Quote retrieval failed - missing required fields")
                
            return success
            
        except Exception as e:
            print(f"  ❌ Quote retrieval failed: {e}")
            self.results["get_quote"] = {"success": False, "error": str(e)}
            return False
            
    def test_get_quote_pdf(self, quote_id: int) -> bool:
        """Test get quote PDF endpoint."""
        print(f"📄 Testing GET /quotes/{quote_id}/pdf")
        try:
            response = self.session.get(f"{self.base_url}/quotes/{quote_id}/pdf")
            response.raise_for_status()
            
            # Validate content type
            content_type = response.headers.get("content-type", "")
            is_pdf = "application/pdf" in content_type
            has_content = len(response.content) > 0
            
            success = is_pdf and has_content
            
            if success:
                self.save_binary(f"quote_{quote_id}.pdf", response.content)
                print(f"  ✅ PDF generated successfully ({len(response.content)} bytes)")
            else:
                print(f"  ❌ PDF generation failed - content-type: {content_type}, size: {len(response.content)}")
            
            self.results["get_quote_pdf"] = {
                "success": success,
                "status": response.status_code,
                "content_type": content_type,
                "size_bytes": len(response.content)
            }
            
            return success
            
        except Exception as e:
            print(f"  ❌ PDF generation failed: {e}")
            self.results["get_quote_pdf"] = {"success": False, "error": str(e)}
            return False
            
    def test_chat(self) -> bool:
        """Test chat endpoint."""
        print("💬 Testing POST /chat")
        try:
            payload = {
                "message": "Create a quote for Acme for 10 Widgets",
                "session_id": f"test-{int(time.time())}"
            }
            
            response = self.session.post(
                f"{self.base_url}/chat",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            data = response.json()
            self.save_json("chat.json", {
                "request": payload,
                "response": data,
                "status_code": response.status_code
            })
            
            # Validate response structure
            success = "response" in data and "session_id" in data
            
            self.results["chat"] = {
                "success": success,
                "status": response.status_code
            }
            
            if success:
                response_text = data.get("response", "")[:100] + "..." if len(data.get("response", "")) > 100 else data.get("response", "")
                print(f"  ✅ Chat response received: {response_text}")
            else:
                print("  ❌ Chat failed - missing required fields")
                
            return success
            
        except Exception as e:
            print(f"  ❌ Chat failed: {e}")
            self.results["chat"] = {"success": False, "error": str(e)}
            return False
            
    def test_chat_stream(self) -> bool:
        """Test chat streaming endpoint."""
        print("🌊 Testing POST /chat")
        try:
            payload = {
                "message": "Create a quote for Acme Ltd for 5 Widget",
                "session_id": f"stream-test-{int(time.time())}"
            }
            
            response = self.session.post(
                f"{self.base_url}/chat",
                json=payload,
                headers={"Content-Type": "application/json"},
                stream=True
            )
            response.raise_for_status()
            
            # Capture streaming response
            stream_content = []
            token_count = 0
            done_received = False
            
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    stream_content.append(line)
                    
                    # Count token events
                    if line.startswith("event: token"):
                        token_count += 1
                    elif line.startswith("event: done"):
                        done_received = True
            
            # Save raw stream content
            stream_text = "\n".join(stream_content)
            self.save_text("chat_stream.txt", stream_text)
            
            # Validate streaming behavior
            has_tokens = token_count > 0
            success = has_tokens and done_received
            
            self.results["chat_stream"] = {
                "success": success,
                "status": response.status_code,
                "token_count": token_count,
                "done_received": done_received
            }
            
            if success:
                print(f"  ✅ Streaming chat successful ({token_count} tokens, done received)")
            else:
                print(f"  ❌ Streaming chat failed - tokens: {token_count}, done: {done_received}")
                
            return success
            
        except Exception as e:
            print(f"  ❌ Streaming chat failed: {e}")
            self.results["chat_stream"] = {"success": False, "error": str(e)}
            return False
            
    def generate_summary(self) -> Dict[str, Any]:
        """Generate test summary."""
        total_tests = len(self.results)
        passed_tests = sum(1 for result in self.results.values() if result.get("success", False))
        
        summary = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "failed_tests": total_tests - passed_tests,
            "success_rate": f"{(passed_tests / total_tests * 100):.1f}%" if total_tests > 0 else "0%",
            "results": self.results
        }
        
        self.save_json("test_summary.json", summary)
        return summary
        
    def run_all_tests(self) -> bool:
        """Run all API tests."""
        print("🚀 Starting API testing...")
        print(f"   Target: {self.base_url}")
        print()
        
        # Test sequence
        success = True
        
        # 1. Health check
        if not self.test_healthz():
            success = False
            
        # 2. Create quote
        quote_id = self.test_create_quote()
        if not quote_id:
            success = False
            return success  # Can't continue without quote_id
            
        # 3. Get quote
        if not self.test_get_quote(quote_id):
            success = False
            
        # 4. Get quote PDF
        if not self.test_get_quote_pdf(quote_id):
            success = False
            
        # 5. Chat (non-streaming)
        if not self.test_chat():
            success = False
            
        # 6. Chat streaming
        if not self.test_chat_stream():
            success = False
            
        print()
        summary = self.generate_summary()
        print("📊 Test Summary:")
        print(f"   ✅ Passed: {summary['passed_tests']}/{summary['total_tests']} ({summary['success_rate']})")
        print(f"   📁 Samples saved to: {self.samples_dir}")
        
        return success


def main():
    """Main function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Capture API samples")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    args = parser.parse_args()
    
    tester = APITester(args.base_url)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
