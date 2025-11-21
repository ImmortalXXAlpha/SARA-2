# ai/ai_tool_coordinator.py
"""
AI Tool Coordinator - Bridges NovaAI with CleanTunePage tools
Allows the AI to interpret user requests and execute system maintenance tasks.
Includes optimizations for faster response times.
"""

import re
import threading
from typing import Optional, Callable, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
from PySide6.QtCore import QObject, Signal

class ToolType(Enum):
    SFC = "sfc"
    DISM = "dism"
    CLEANUP = "cleanup"
    SMARTSCAN = "smartscan"
    NONE = "none"

@dataclass
class ToolMatch:
    tool: ToolType
    confidence: float  # 0.0 - 1.0
    reason: str

class AIToolCoordinator(QObject):
    """
    Coordinates between AI chat and system tools.
    Uses fast keyword matching first, falls back to AI interpretation for ambiguous requests.
    """
    # Signals for UI integration
    tool_requested = Signal(str, dict)  # tool_name, options
    status_update = Signal(str)
    
    # Keyword patterns for fast matching (no AI inference needed)
    TOOL_PATTERNS = {
        ToolType.SFC: {
            "keywords": ["sfc", "system file checker", "repair system files", "corrupted files", 
                        "fix windows files", "scan system", "scannow", "repair windows"],
            "weight": 1.0
        },
        ToolType.DISM: {
            "keywords": ["dism", "system image", "restore health", "repair image", 
                        "windows image", "component store", "fix image"],
            "weight": 1.0
        },
        ToolType.CLEANUP: {
            "keywords": ["cleanup", "clean up", "temp files", "temporary files", "clear cache",
                        "delete temp", "free space", "disk cleanup", "prefetch", "junk files"],
            "weight": 1.0
        },
        ToolType.SMARTSCAN: {
            "keywords": ["virus", "malware", "virustotal", "scan files", "smartscan", 
                        "check for virus", "security scan", "infected", "threat"],
            "weight": 1.0
        }
    }
    
    # Tool display names mapping
    TOOL_DISPLAY_NAMES = {
        ToolType.SFC: "System File Checker (SFC)",
        ToolType.DISM: "DISM Repair",
        ToolType.CLEANUP: "Cleanup Temp Files",
        ToolType.SMARTSCAN: "SmartScan (VirusTotal)"
    }

    def __init__(self, ai=None, clean_tune_page=None):
        super().__init__()
        self.ai = ai
        self.clean_tune_page = clean_tune_page
        self._pending_confirmation = None
        
    def set_ai(self, ai):
        self.ai = ai
        
    def set_clean_tune_page(self, page):
        self.clean_tune_page = page

    def process_message(self, user_input: str) -> Tuple[str, Optional[ToolMatch]]:
        """
        Process user message and determine if a tool should be run.
        Returns (response_text, tool_match or None)
        
        Uses fast keyword matching first - only uses AI for ambiguous cases.
        """
        lower = user_input.lower().strip()
        
        # Check for confirmation of pending action
        if self._pending_confirmation:
            if self._is_confirmation(lower):
                tool = self._pending_confirmation
                self._pending_confirmation = None
                return self._execute_tool(tool)
            elif self._is_rejection(lower):
                self._pending_confirmation = None
                return ("Okay, I won't run that tool. What else can I help with?", None)
        
        # Fast keyword matching
        match = self._fast_match(lower)
        
        if match and match.confidence >= 0.7:
            # High confidence - ask for confirmation
            self._pending_confirmation = match.tool
            tool_name = self.TOOL_DISPLAY_NAMES.get(match.tool, str(match.tool))
            return (f"I can run **{tool_name}** for you. {match.reason}\n\nWould you like me to start it? (yes/no)", match)
        
        elif match and match.confidence >= 0.4:
            # Medium confidence - clarify
            tool_name = self.TOOL_DISPLAY_NAMES.get(match.tool, str(match.tool))
            return (f"It sounds like you might want to run **{tool_name}**. Is that correct? (yes/no)", match)
        
        # No tool match - return None so normal AI chat can handle it
        return (None, None)

    def _fast_match(self, text: str) -> Optional[ToolMatch]:
        """Fast keyword-based matching without AI inference."""
        scores = {}
        
        for tool_type, config in self.TOOL_PATTERNS.items():
            score = 0
            matched_keywords = []
            
            for keyword in config["keywords"]:
                if keyword in text:
                    # Longer keywords get more weight
                    weight = len(keyword.split()) * 0.3 + 0.7
                    score += weight
                    matched_keywords.append(keyword)
            
            if score > 0:
                scores[tool_type] = (score, matched_keywords)
        
        if not scores:
            return None
        
        # Get highest scoring tool
        best_tool = max(scores, key=lambda t: scores[t][0])
        best_score, keywords = scores[best_tool]
        
        # Normalize confidence (cap at 1.0)
        confidence = min(1.0, best_score / 2.0)
        
        reasons = {
            ToolType.SFC: "This will scan and repair corrupted Windows system files.",
            ToolType.DISM: "This will repair the Windows system image using DISM.",
            ToolType.CLEANUP: "This will remove temporary files and free up disk space.",
            ToolType.SMARTSCAN: "This will check your files against VirusTotal for threats."
        }
        
        return ToolMatch(
            tool=best_tool,
            confidence=confidence,
            reason=reasons.get(best_tool, "")
        )

    def _is_confirmation(self, text: str) -> bool:
        confirmations = ["yes", "y", "yeah", "yep", "sure", "ok", "okay", "go ahead", 
                        "do it", "run it", "start", "proceed", "please", "affirmative"]
        return any(c in text for c in confirmations)

    def _is_rejection(self, text: str) -> bool:
        rejections = ["no", "n", "nope", "cancel", "stop", "don't", "nevermind", "never mind"]
        return any(r in text for r in rejections)

    def _execute_tool(self, tool: ToolType) -> Tuple[str, ToolMatch]:
        """Execute the specified tool via CleanTunePage."""
        tool_name = self.TOOL_DISPLAY_NAMES.get(tool)
        
        if not tool_name:
            return ("Sorry, I couldn't identify which tool to run.", None)
        
        if not self.clean_tune_page:
            return (f"I'd run {tool_name}, but the system tools aren't connected yet.", None)
        
        # Emit signal for UI to handle (thread-safe)
        self.tool_requested.emit(tool_name, {})
        self.status_update.emit(f"Starting {tool_name}...")
        
        return (f"✅ Starting **{tool_name}**. I've opened the tool window - you can monitor progress there.", 
                ToolMatch(tool=tool, confidence=1.0, reason="Executed"))

    def get_available_tools_description(self) -> str:
        """Return a description of available tools for the AI system prompt."""
        return """You can help users run these system maintenance tools:
1. System File Checker (SFC) - Scans and repairs corrupted Windows system files
2. DISM Repair - Repairs the Windows system image  
3. Cleanup Temp Files - Removes temporary files, caches, and frees disk space
4. SmartScan (VirusTotal) - Checks files for malware using VirusTotal

When a user asks about system repair, cleanup, or security scanning, suggest the appropriate tool."""


class OptimizedAIWorker(QObject):
    """
    Optimized AI worker that handles tool coordination and generation.
    Runs keyword matching on main thread (fast), AI inference in background.
    """
    response_ready = Signal(str)
    tool_triggered = Signal(str, dict)
    
    def __init__(self, ai, coordinator: AIToolCoordinator, prompt: str, 
                 max_new_tokens: int = 256, temperature: float = 0.7):
        super().__init__()
        self.ai = ai
        self.coordinator = coordinator
        self.prompt = prompt
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self._stopped = False

    def stop(self):
        self._stopped = True

    def process(self):
        """Process the message - first check tools, then AI if needed."""
        # Step 1: Fast tool matching (no AI needed)
        tool_response, tool_match = self.coordinator.process_message(self.prompt)
        
        if tool_response:
            # Tool was matched - return immediately without AI inference
            self.response_ready.emit(tool_response)
            return
        
        # Step 2: No tool match - run AI inference in background thread
        if self._stopped:
            return
            
        def _generate():
            if self._stopped:
                return
            result = self.ai.generate(
                self.prompt, 
                max_new_tokens=self.max_new_tokens, 
                temperature=self.temperature
            )
            if not self._stopped:
                self.response_ready.emit(result)
        
        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()