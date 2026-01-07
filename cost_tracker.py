"""
cost_tracker.py - API Usage and Cost Tracking

Tracks API calls and estimates costs for:
- Fal.ai (Image generation, Video generation, TTS)
- Google Gemini (Text generation, Vision)
- Google Cloud Storage (uploads)

This is a lightweight, non-invasive tracker that can be imported
and used anywhere in the codebase.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List
from threading import Lock


# =============================================================================
# Pricing Configuration (as of Jan 2026)
# =============================================================================
# These are estimates - actual pricing may vary

PRICING = {
    # Fal.ai pricing (per call/request)
    "fal-ai/nano-banana-pro": 0.01,           # ~$0.01 per image
    "fal-ai/nano-banana-pro/edit": 0.015,     # ~$0.015 per edit
    "fal-ai/flux-pro": 0.05,                  # ~$0.05 per image
    "fal-ai/flux-2-pro": 0.05,                # ~$0.05 per image
    "fal-ai/flux-pro/kontext": 0.03,          # ~$0.03 per edit
    "fal-ai/kling-video/v1.6/pro/image-to-video": 0.10,  # ~$0.10 per 5s video
    "fal-ai/elevenlabs/tts": 0.01,            # ~$0.01 per 1000 chars
    
    # Gemini pricing (per 1M tokens - we'll estimate tokens)
    "gemini-2.0-flash": {
        "input": 0.075 / 1_000_000,           # $0.075 per 1M input tokens
        "output": 0.30 / 1_000_000,           # $0.30 per 1M output tokens
    },
    "gemini-2.5-flash": {
        "input": 0.15 / 1_000_000,
        "output": 0.60 / 1_000_000,
    },
    
    # GCS pricing
    "gcs-upload-per-gb": 0.12,                # ~$0.12 per GB stored
}


@dataclass
class APICall:
    """Record of a single API call."""
    timestamp: str
    service: str       # "fal", "gemini", "gcs"
    model: str         # e.g., "fal-ai/nano-banana-pro"
    scenario_id: str
    operation: str     # e.g., "text_to_image", "image_to_video", "tts"
    estimated_cost: float
    metadata: Dict = field(default_factory=dict)


class CostTracker:
    """
    Singleton cost tracker that logs API calls and estimates costs.
    
    Usage:
        from cost_tracker import cost_tracker
        cost_tracker.log_fal_call("fal-ai/nano-banana-pro", scenario_id, "text_to_image")
        cost_tracker.log_gemini_call("gemini-2.0-flash", scenario_id, input_tokens, output_tokens)
        
        # At end of session
        cost_tracker.print_summary()
        cost_tracker.save_to_file()
    """
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.calls: List[APICall] = []
        self.session_start = datetime.now().isoformat()
        self._initialized = True
    
    def log_fal_call(
        self,
        model: str,
        scenario_id: str,
        operation: str,
        metadata: Optional[Dict] = None
    ) -> float:
        """
        Log a Fal.ai API call.
        
        Args:
            model: Fal model name (e.g., "fal-ai/nano-banana-pro")
            scenario_id: Current scenario ID
            operation: Type of operation (e.g., "text_to_image", "image_to_video")
            metadata: Optional extra info (dimensions, duration, etc.)
            
        Returns:
            Estimated cost of this call
        """
        # Look up pricing
        cost = PRICING.get(model, 0.01)  # Default to $0.01 if unknown
        
        # Adjust for video duration if applicable
        if metadata and "duration_seconds" in metadata:
            # Video costs scale with duration (base rate is for 5s)
            duration = metadata["duration_seconds"]
            cost = cost * (duration / 5.0)
        
        call = APICall(
            timestamp=datetime.now().isoformat(),
            service="fal",
            model=model,
            scenario_id=scenario_id,
            operation=operation,
            estimated_cost=cost,
            metadata=metadata or {}
        )
        self.calls.append(call)
        return cost
    
    def log_gemini_call(
        self,
        model: str,
        scenario_id: str,
        operation: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        metadata: Optional[Dict] = None
    ) -> float:
        """
        Log a Gemini API call.
        
        Args:
            model: Gemini model name
            scenario_id: Current scenario ID
            operation: Type of operation (e.g., "screenplay", "vision_gate", "prompt_improve")
            input_tokens: Estimated input tokens
            output_tokens: Estimated output tokens
            
        Returns:
            Estimated cost of this call
        """
        pricing = PRICING.get(model, {"input": 0.0001, "output": 0.0003})
        
        if isinstance(pricing, dict):
            cost = (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])
        else:
            cost = pricing
        
        call = APICall(
            timestamp=datetime.now().isoformat(),
            service="gemini",
            model=model,
            scenario_id=scenario_id,
            operation=operation,
            estimated_cost=cost,
            metadata={"input_tokens": input_tokens, "output_tokens": output_tokens, **(metadata or {})}
        )
        self.calls.append(call)
        return cost
    
    def log_gcs_upload(
        self,
        scenario_id: str,
        file_size_bytes: int,
        file_type: str = "video"
    ) -> float:
        """
        Log a GCS upload.
        
        Args:
            scenario_id: Current scenario ID
            file_size_bytes: Size of uploaded file
            file_type: Type of file (video, image, audio)
            
        Returns:
            Estimated monthly storage cost
        """
        size_gb = file_size_bytes / (1024 ** 3)
        cost = size_gb * PRICING["gcs-upload-per-gb"]
        
        call = APICall(
            timestamp=datetime.now().isoformat(),
            service="gcs",
            model="storage",
            scenario_id=scenario_id,
            operation=f"upload_{file_type}",
            estimated_cost=cost,
            metadata={"file_size_bytes": file_size_bytes, "file_type": file_type}
        )
        self.calls.append(call)
        return cost
    
    def get_session_total(self) -> float:
        """Get total estimated cost for this session."""
        return sum(call.estimated_cost for call in self.calls)
    
    def get_scenario_total(self, scenario_id: str) -> float:
        """Get total estimated cost for a specific scenario."""
        return sum(call.estimated_cost for call in self.calls if call.scenario_id == scenario_id)
    
    def get_breakdown_by_service(self) -> Dict[str, float]:
        """Get cost breakdown by service (fal, gemini, gcs)."""
        breakdown = {}
        for call in self.calls:
            breakdown[call.service] = breakdown.get(call.service, 0) + call.estimated_cost
        return breakdown
    
    def get_breakdown_by_operation(self) -> Dict[str, float]:
        """Get cost breakdown by operation type."""
        breakdown = {}
        for call in self.calls:
            breakdown[call.operation] = breakdown.get(call.operation, 0) + call.estimated_cost
        return breakdown
    
    def print_summary(self) -> None:
        """Print a summary of costs to console."""
        total = self.get_session_total()
        by_service = self.get_breakdown_by_service()
        by_operation = self.get_breakdown_by_operation()
        
        print("\n" + "=" * 60)
        print("💰 COST TRACKING SUMMARY")
        print("=" * 60)
        print(f"   Session Start: {self.session_start}")
        print(f"   Total API Calls: {len(self.calls)}")
        print(f"   Estimated Total Cost: ${total:.4f}")
        print()
        
        if by_service:
            print("   📊 By Service:")
            for service, cost in sorted(by_service.items(), key=lambda x: -x[1]):
                print(f"      {service}: ${cost:.4f}")
        
        if by_operation:
            print("\n   📊 By Operation:")
            for op, cost in sorted(by_operation.items(), key=lambda x: -x[1]):
                print(f"      {op}: ${cost:.4f}")
        
        print("=" * 60 + "\n")
    
    def save_to_file(self, output_dir: Optional[Path] = None) -> str:
        """
        Save cost tracking data to a JSON file.
        
        Args:
            output_dir: Directory to save to (defaults to ./output/)
            
        Returns:
            Path to the saved file
        """
        output_dir = output_dir or Path("output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_dir / f"cost_log_{timestamp}.json"
        
        data = {
            "session_start": self.session_start,
            "session_end": datetime.now().isoformat(),
            "total_calls": len(self.calls),
            "estimated_total_cost": self.get_session_total(),
            "breakdown_by_service": self.get_breakdown_by_service(),
            "breakdown_by_operation": self.get_breakdown_by_operation(),
            "calls": [asdict(call) for call in self.calls]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"💾 Cost log saved to: {filename}")
        return str(filename)
    
    def reset(self) -> None:
        """Reset the tracker for a new session."""
        self.calls = []
        self.session_start = datetime.now().isoformat()


# Global singleton instance
cost_tracker = CostTracker()


# =============================================================================
# Convenience functions for common operations
# =============================================================================

def log_image_generation(model: str, scenario_id: str, stage: int = 0) -> float:
    """Log an image generation call."""
    return cost_tracker.log_fal_call(
        model=model,
        scenario_id=scenario_id,
        operation="text_to_image" if stage == 1 else "image_to_image",
        metadata={"stage": stage}
    )

def log_video_generation(model: str, scenario_id: str, duration: float = 5.0) -> float:
    """Log a video generation call."""
    return cost_tracker.log_fal_call(
        model=model,
        scenario_id=scenario_id,
        operation="image_to_video",
        metadata={"duration_seconds": duration}
    )

def log_tts_generation(scenario_id: str, text_length: int = 0) -> float:
    """Log a TTS call."""
    return cost_tracker.log_fal_call(
        model="fal-ai/elevenlabs/tts",
        scenario_id=scenario_id,
        operation="tts",
        metadata={"text_length": text_length}
    )

def log_gemini_screenplay(scenario_id: str) -> float:
    """Log a screenwriter call (estimate: ~500 input, ~1000 output tokens)."""
    return cost_tracker.log_gemini_call(
        model="gemini-2.0-flash",
        scenario_id=scenario_id,
        operation="screenplay",
        input_tokens=500,
        output_tokens=1000
    )

def log_gemini_vision(scenario_id: str) -> float:
    """Log a vision gate call (estimate: ~1000 input for image, ~200 output)."""
    return cost_tracker.log_gemini_call(
        model="gemini-2.0-flash",
        scenario_id=scenario_id,
        operation="vision_gate",
        input_tokens=1000,
        output_tokens=200
    )

def log_gemini_prompt_improve(scenario_id: str) -> float:
    """Log a prompt improvement call (estimate: ~300 input, ~500 output)."""
    return cost_tracker.log_gemini_call(
        model="gemini-2.0-flash",
        scenario_id=scenario_id,
        operation="prompt_improve",
        input_tokens=300,
        output_tokens=500
    )


if __name__ == "__main__":
    # Test the tracker
    print("Testing Cost Tracker...")
    
    # Simulate a scenario
    test_id = "scenario_test"
    
    log_gemini_screenplay(test_id)
    log_image_generation("fal-ai/nano-banana-pro", test_id, stage=1)
    log_image_generation("fal-ai/nano-banana-pro/edit", test_id, stage=2)
    log_image_generation("fal-ai/nano-banana-pro/edit", test_id, stage=3)
    log_gemini_vision(test_id)
    log_video_generation("fal-ai/kling-video/v1.6/pro/image-to-video", test_id, duration=5.0)
    log_video_generation("fal-ai/kling-video/v1.6/pro/image-to-video", test_id, duration=5.0)
    log_video_generation("fal-ai/kling-video/v1.6/pro/image-to-video", test_id, duration=5.0)
    log_tts_generation(test_id, text_length=500)
    cost_tracker.log_gcs_upload(test_id, 15_000_000, "video")  # 15MB video
    
    cost_tracker.print_summary()
