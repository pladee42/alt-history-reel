"""
kie_client.py - Kie.ai API Client

Provides a unified interface to Kie.ai API for:
- Text-to-Image (nano-banana-pro)
- Image-to-Image (nano-banana-pro with image_urls)
- Image-to-Video (Seedance 1.5 Pro with optional audio)

API Documentation: https://kie.ai/docs
"""

import os
import time
import base64
import requests
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)


@dataclass
class KieImageResult:
    """Result from image generation."""
    image_url: str
    task_id: str


@dataclass
class KieVideoResult:
    """Result from video generation."""
    video_url: str
    task_id: str
    has_audio: bool = False


class KieClient:
    """
    Client for Kie.ai API with task polling.
    
    Usage:
        client = KieClient()
        
        # Text-to-image
        result = client.generate_image("a sunset over mountains", aspect_ratio="9:16")
        
        # Image-to-image
        result = client.edit_image("add rain", reference_image_path="input.png")
        
        # Image-to-video
        result = client.generate_video("slow zoom in", image_path="frame.png", generate_audio=True)
    """
    
    BASE_URL = "https://api.kie.ai/api/v1"
    
    def __init__(self):
        """Initialize client with API key from environment."""
        self.api_key = os.getenv("KIE_AI_KEY")
        if not self.api_key:
            raise ValueError("KIE_AI_KEY not found in environment")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        print(f"🔌 Kie.ai client initialized")
    
    # =========================================================================
    # Core API Methods
    # =========================================================================
    
    def create_task(self, model: str, params: Dict[str, Any]) -> str:
        """
        Create a generation task and return task_id.
        
        Args:
            model: Model name (e.g., "nano-banana-pro", "bytedance/seedance-1.5-pro")
            params: Model-specific parameters
            
        Returns:
            task_id for polling
        """
        payload = {
            "model": model,
            "input": params
        }
        
        response = requests.post(
            f"{self.BASE_URL}/jobs/createTask",
            headers=self.headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Handle nested response: {'code': 200, 'data': {'taskId': ...}}
        # Note: data can be None explicitly, so check for that
        data = result.get("data")
        if data is None:
            data = result  # Fall back to result if data is None or missing
        
        task_id = data.get("taskId") or data.get("task_id") or result.get("taskId") or result.get("task_id")
        
        if not task_id:
            raise ValueError(f"No task_id in response: {result}")
        
        return task_id
    
    def query_task(self, task_id: str) -> Dict[str, Any]:
        """
        Query task status and result.
        
        Args:
            task_id: Task ID from create_task
            
        Returns:
            Task status and output if completed (normalized from 'data' wrapper)
        """
        response = requests.get(
            f"{self.BASE_URL}/jobs/recordInfo",  # Correct endpoint
            headers=self.headers,
            params={"taskId": task_id},  # Correct parameter name
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        # Handle nested response: {'code': 200, 'data': {'status': ..., 'output': ...}}
        # Note: data can be None explicitly, so check for that
        data = result.get("data")
        if data is None:
            data = result  # Fall back to result if data is None or missing
        return data
    
    def wait_for_completion(
        self, 
        task_id: str, 
        timeout: int = 300, 
        poll_interval: int = 3
    ) -> Dict[str, Any]:
        """
        Poll until task completes or timeout.
        
        Args:
            task_id: Task ID to poll
            timeout: Maximum wait time in seconds
            poll_interval: Time between polls in seconds
            
        Returns:
            Completed task result with output
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            result = self.query_task(task_id)
            
            # Kie.ai uses 'state' field, but check 'status' as fallback
            status = (result.get("state") or result.get("status") or "").lower()
            
            if status in ["completed", "success", "done"]:
                return result
            
            if status in ["failed", "error", "fail"]:
                error_msg = result.get("error") or result.get("message") or result.get("failMsg") or "Unknown error"
                raise RuntimeError(f"Task {task_id} failed: {error_msg}")
            
            # Still processing (generating, pending, etc.)
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Task {task_id} timed out after {timeout}s")
    
    # =========================================================================
    # Image Upload Helpers
    # =========================================================================
    
    def _encode_image_base64(self, image_path: str) -> str:
        """Encode a local image to base64 data URI."""
        path = Path(image_path)
        
        # Determine MIME type
        suffix = path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg", 
            ".jpeg": "image/jpeg",
            ".webp": "image/webp"
        }
        mime_type = mime_types.get(suffix, "image/png")
        
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        
        return f"data:{mime_type};base64,{encoded}"
    
    def _upload_to_kie(self, image_path: str) -> str:
        """
        Upload image to Kie.ai and get a URL.
        
        Note: If Kie.ai has an upload endpoint, use it here.
        Otherwise, fall back to base64 encoding.
        """
        # For now, use base64 encoding which Kie.ai accepts
        return self._encode_image_base64(image_path)
    
    # =========================================================================
    # High-Level Image Methods
    # =========================================================================
    
    def _extract_result_url(self, result: Dict[str, Any], url_type: str = "image") -> str:
        """
        Extract URL from Kie.ai result response.
        
        Kie.ai returns URLs in 'resultJson' as a JSON string:
        {'resultJson': '{"resultUrls":["https://..."]}'}
        
        Args:
            result: Result dict from wait_for_completion
            url_type: "image" or "video" for error messages
            
        Returns:
            Extracted URL string
        """
        import json
        
        # Try resultJson first (most common)
        result_json_str = result.get("resultJson")
        if result_json_str:
            try:
                result_json = json.loads(result_json_str)
                urls = result_json.get("resultUrls") or result_json.get("resultImageUrl") or []
                if urls:
                    return urls[0] if isinstance(urls, list) else urls
                # Also check for video URLs
                video_url = result_json.get("resultVideoUrl") or result_json.get("videoUrl")
                if video_url:
                    return video_url
            except json.JSONDecodeError:
                pass
        
        # Fallback: try direct output field
        output = result.get("output", {})
        if isinstance(output, dict):
            url = output.get("image_url") or output.get("url") or output.get("video_url")
            if url:
                return url
            images = output.get("images") or output.get("image_urls") or []
            if images:
                return images[0] if isinstance(images[0], str) else images[0].get("url")
        
        raise ValueError(f"No {url_type} URL in response: {result}")
    
    def generate_image(
        self, 
        prompt: str, 
        aspect_ratio: str = "9:16",
        resolution: str = "1K"
    ) -> KieImageResult:
        """
        Generate an image from text using nano-banana-pro.
        
        Args:
            prompt: Text description of the image
            aspect_ratio: Output aspect ratio (9:16, 16:9, 1:1, etc.)
            resolution: Output resolution (1K, 2K, 4K)
            
        Returns:
            KieImageResult with image URL
        """
        print(f"   🖼️ Kie.ai: Generating image (nano-banana-pro)...")
        
        task_id = self.create_task("nano-banana-pro", {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "num_images": 1
        })
        
        result = self.wait_for_completion(task_id)
        image_url = self._extract_result_url(result, "image")
        
        print(f"      ✅ Image generated")
        
        return KieImageResult(image_url=image_url, task_id=task_id)
    
    def edit_image(
        self, 
        prompt: str, 
        reference_image_url: str,
        aspect_ratio: str = "9:16",
        resolution: str = "1K"
    ) -> KieImageResult:
        """
        Edit/transform an image using nano-banana-pro.
        
        Args:
            prompt: Edit instructions
            reference_image_url: URL to the reference image (NOT base64)
            aspect_ratio: Output aspect ratio
            resolution: Output resolution
            
        Returns:
            KieImageResult with edited image URL
        """
        print(f"   🖼️ Kie.ai: Editing image (nano-banana-pro)...")
        
        # Kie.ai expects image URLs, not base64 encoded data
        task_id = self.create_task("nano-banana-pro", {
            "prompt": prompt,
            "image_urls": [reference_image_url],  # Must be a URL
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "num_images": 1
        })
        
        result = self.wait_for_completion(task_id)
        image_url = self._extract_result_url(result, "image")
        
        print(f"      ✅ Image edited")
        
        return KieImageResult(image_url=image_url, task_id=task_id)
    
    # =========================================================================
    # High-Level Video Methods
    # =========================================================================
    
    def generate_video(
        self,
        prompt: str,
        image_url: str,
        duration: int = 5,
        resolution: str = "720p",
        aspect_ratio: str = "9:16",
        generate_audio: bool = True
    ) -> KieVideoResult:
        """
        Generate video from image using Seedance 1.5 Pro.
        
        Args:
            prompt: Motion/action description
            image_url: URL to the input image (NOT base64)
            duration: Video duration in seconds (4-12)
            resolution: Output resolution (480p, 720p, 1080p)
            aspect_ratio: Output aspect ratio
            generate_audio: Whether to generate synchronized audio
            
        Returns:
            KieVideoResult with video URL and audio info
        """
        print(f"   🎥 Kie.ai: Generating video (seedance-1.5-pro)...")
        
        # Kie.ai expects image URLs for Seedance 1.5 Pro
        task_id = self.create_task("bytedance/seedance-1.5-pro", {
            "prompt": prompt,
            "image": image_url,  # Pass URL directly
            "duration": str(duration),  # Kie.ai expects duration as string
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "generate_audio": generate_audio
        })
        
        # Video generation takes longer
        result = self.wait_for_completion(task_id, timeout=600, poll_interval=5)
        video_url = self._extract_result_url(result, "video")
        
        print(f"      ✅ Video generated" + (" (with audio)" if generate_audio else ""))
        
        return KieVideoResult(
            video_url=video_url,
            task_id=task_id,
            has_audio=generate_audio
        )
    
    # =========================================================================
    # Veo3 Video Methods (Different API endpoint)
    # =========================================================================
    
    def generate_video_veo3(
        self,
        prompt: str,
        image_url: str,
        model: str = "veo3_fast",
        aspect_ratio: str = "9:16",
        enable_translation: bool = True
    ) -> KieVideoResult:
        """
        Generate video from image using Google Veo 3.1.
        
        Uses different endpoint: POST /api/v1/veo/generate
        
        Args:
            prompt: Motion/action description
            image_url: URL to the input image
            model: "veo3" (quality) or "veo3_fast" (faster)
            aspect_ratio: "16:9", "9:16", or "Auto"
            enable_translation: Auto-translate non-English prompts
            
        Returns:
            KieVideoResult with video URL
        """
        print(f"   🎥 Kie.ai: Generating video (Veo 3.1 {model})...")
        
        payload = {
            "prompt": prompt,
            "imageUrls": [image_url],  # Veo3 uses array of URLs
            "model": model,
            "aspect_ratio": aspect_ratio,
            "enableTranslation": enable_translation,
            "generationType": "REFERENCE_2_VIDEO"  # Reference-based for better image adherence
        }
        
        response = requests.post(
            f"{self.BASE_URL}/veo/generate",
            headers=self.headers,
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Extract task ID from response
        data = result.get("data", {})
        task_id = data.get("taskId")
        
        if not task_id:
            raise ValueError(f"No taskId in Veo3 response: {result}")
        
        print(f"      📋 Task ID: {task_id}")
        
        # Wait for completion using Veo3-specific polling
        completion = self._wait_for_veo3_completion(task_id)
        video_url = self._extract_veo3_video_url(completion)
        
        print(f"      ✅ Video generated")
        
        return KieVideoResult(
            video_url=video_url,
            task_id=task_id,
            has_audio=True  # Veo3.1 embeds audio
        )
    
    def _wait_for_veo3_completion(
        self, 
        task_id: str, 
        timeout: int = 600, 
        poll_interval: int = 5
    ) -> Dict[str, Any]:
        """
        Poll Veo3 task status using /api/v1/veo/record-info.
        
        Status codes (successFlag):
        - 0: Generating
        - 1: Success
        - 2: Failed
        - 3: Generation Failed
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = requests.get(
                f"{self.BASE_URL}/veo/record-info",
                headers=self.headers,
                params={"taskId": task_id},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            # Handle case where data is explicitly null
            data = result.get("data")
            if data is None:
                # API returned null data, may still be processing
                time.sleep(poll_interval)
                continue
            
            success_flag = data.get("successFlag")
            
            if success_flag == 1:
                return data
            
            if success_flag in [2, 3]:
                error_msg = data.get("errorMessage") or data.get("errorCode") or "Unknown error"
                raise RuntimeError(f"Veo3 task {task_id} failed: {error_msg}")
            
            # Still generating (successFlag == 0 or None)
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Veo3 task {task_id} timed out after {timeout}s")
    
    def _extract_veo3_video_url(self, data: Dict[str, Any]) -> str:
        """Extract video URL from Veo3 completion response."""
        response = data.get("response", {})
        
        # Try resultUrls first
        result_urls = response.get("resultUrls") or []
        if result_urls:
            return result_urls[0]
        
        # Try originUrls as fallback
        origin_urls = response.get("originUrls") or []
        if origin_urls:
            return origin_urls[0]
        
        raise ValueError(f"No video URL in Veo3 response: {data}")


# Global singleton - only created if KIE_AI_KEY is set
def get_kie_client() -> Optional[KieClient]:
    """Get the Kie.ai client if API key is configured."""
    if os.getenv("KIE_AI_KEY"):
        return KieClient()
    return None


if __name__ == "__main__":
    # Quick connectivity test
    print("=" * 50)
    print("🧪 Testing Kie.ai Client")
    print("=" * 50)
    
    api_key = os.getenv("KIE_AI_KEY")
    if not api_key:
        print("❌ KIE_AI_KEY not set in environment")
        print("   Add it to your .env file to test the client")
    else:
        print(f"✅ KIE_AI_KEY is configured")
        print(f"   Key prefix: {api_key[:8]}...")
        
        # Try to initialize client
        try:
            client = KieClient()
            print("✅ Client initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize client: {e}")
