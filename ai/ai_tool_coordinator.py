# ai/ai_tool_coordinator.py
"""
AI Tool Coordinator - Works with smart completion detection.
No more hardcoded delays - tools advance when they actually complete.
"""

import re
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from enum import Enum
from PySide6.QtCore import QObject, Signal, QTimer

class ToolType(Enum):
    SFC = "sfc"
    DISM = "dism"
    CLEANUP = "cleanup"
    SMARTSCAN = "smartscan"
    NONE = "none"

@dataclass
class ToolWorkflow:
    """Represents a sequence of tools to run."""
    tools: List[ToolType]
    descriptions: Dict[ToolType, str]
    current_index: int = 0
    results: List[Dict] = None
    
    def __post_init__(self):
        if self.results is None:
            self.results = []
    
    def is_complete(self) -> bool:
        return self.current_index >= len(self.tools)
    
    def get_current_tool(self) -> Optional[ToolType]:
        if self.is_complete():
            return None
        return self.tools[self.current_index]
    
    def advance(self):
        self.current_index += 1
    
    def add_result(self, tool: ToolType, success: bool, message: str):
        self.results.append({
            'tool': tool,
            'success': success,
            'message': message
        })


class AIToolCoordinator(QObject):
    """
    Coordinates between AI chat and system tools with workflow support.
    Uses smart detection to know when tools actually complete.
    """
    # Signals
    tool_workflow_started = Signal(list)
    tool_started = Signal(str)
    tool_completed = Signal(str, bool, str)
    workflow_completed = Signal(str)
    ai_message = Signal(str)
    
    TOOL_DISPLAY_NAMES = {
        ToolType.SFC: "System File Checker (SFC)",
        ToolType.DISM: "DISM Repair",
        ToolType.CLEANUP: "Cleanup Temp Files",
        ToolType.SMARTSCAN: "SmartScan (VirusTotal)"
    }
    
    TOOL_DESCRIPTIONS = {
        ToolType.SFC: "Scans and repairs corrupted Windows system files",
        ToolType.DISM: "Repairs the Windows system image and component store",
        ToolType.CLEANUP: "Removes temporary files, caches, and frees disk space",
        ToolType.SMARTSCAN: "Checks files for malware using VirusTotal database"
    }

    def __init__(self, ai=None, clean_tune_page=None):
        super().__init__()
        self.ai = ai
        self.clean_tune_page = clean_tune_page
        
        self.current_workflow: Optional[ToolWorkflow] = None
        self.waiting_for_confirmation = False
        self.pending_workflow: Optional[ToolWorkflow] = None
        self._tool_windows = {}
        
    def set_ai(self, ai):
        self.ai = ai
        
    def set_clean_tune_page(self, page):
        self.clean_tune_page = page

    def reset(self):
        """Reset coordinator state."""
        self.current_workflow = None
        self.waiting_for_confirmation = False
        self.pending_workflow = None
        self._tool_windows = {}
        if self.clean_tune_page:
            self.clean_tune_page._in_workflow_mode = False

    def process_message(self, user_input: str, conversation_history: List[Dict]) -> Optional[str]:
        """Process user message with conversation context."""
        lower = user_input.lower().strip()
        
        if self.waiting_for_confirmation and self.pending_workflow:
            if self._is_confirmation(lower):
                self.waiting_for_confirmation = False
                workflow = self.pending_workflow
                self.pending_workflow = None
                return self._start_workflow(workflow)
            elif self._is_rejection(lower):
                self.waiting_for_confirmation = False
                self.pending_workflow = None
                return "Okay, I won't run those tools. Let me know if you need anything else!"
        
        tools = self._detect_tools(lower, conversation_history)
        
        if tools:
            workflow = ToolWorkflow(
                tools=tools,
                descriptions={t: self.TOOL_DESCRIPTIONS[t] for t in tools}
            )
            
            response = self._build_confirmation_message(workflow)
            self.pending_workflow = workflow
            self.waiting_for_confirmation = True
            
            return response
        
        return None

    def _detect_tools(self, text: str, history: List[Dict]) -> List[ToolType]:
        """Detect which tools user wants to run."""
        tools = []
        
        if any(kw in text for kw in ["maintenance", "full maintenance", "system maintenance", "complete maintenance"]):
            return [ToolType.SFC, ToolType.DISM, ToolType.CLEANUP, ToolType.SMARTSCAN]
        
        if any(kw in text for kw in ["clean", "cleanup", "clear cache", "temp files", "free space", "disk cleanup"]):
            tools.append(ToolType.CLEANUP)
        
        if any(kw in text for kw in ["virus", "malware", "scan", "security", "threat", "infected"]):
            if ToolType.SMARTSCAN not in tools:
                tools.append(ToolType.SMARTSCAN)
        
        if any(kw in text for kw in ["repair", "fix", "corrupted", "system files", "sfc"]):
            if ToolType.SFC not in tools:
                tools.append(ToolType.SFC)
        
        if any(kw in text for kw in ["dism", "system image", "component store"]):
            if ToolType.DISM not in tools:
                tools.append(ToolType.DISM)
        
        if not tools and any(kw in text for kw in ["optimize", "tune", "improve performance", "speed up"]):
            return [ToolType.CLEANUP, ToolType.SFC, ToolType.DISM]
        
        return tools

    def _build_confirmation_message(self, workflow: ToolWorkflow) -> str:
        """Build confirmation message."""
        lines = ["Sure! I can help with that. Here's what I'll do:\n"]
        
        for i, tool in enumerate(workflow.tools, 1):
            tool_name = self.TOOL_DISPLAY_NAMES[tool]
            desc = workflow.descriptions[tool]
            lines.append(f"{i}. **{tool_name}**")
            lines.append(f"   {desc}\n")
        
        lines.append(
            "I'll run these tools one at a time in the order shown above. "
            "Each tool will complete before the next one starts. "
            "Tool windows will close automatically when they finish.\n"
        )
        
        lines.append("**Are you ready to proceed?** (yes/no)")
        
        return "\n".join(lines)

    def _is_confirmation(self, text: str) -> bool:
        """Check if message is a confirmation."""
        confirmations = [
            "yes", "y", "yeah", "yep", "sure", "ok", "okay", "go ahead",
            "do it", "run it", "start", "proceed", "please", "affirmative", "yup"
        ]
        words = text.split()
        return any(c in words or c == text for c in confirmations)

    def _is_rejection(self, text: str) -> bool:
        """Check if message is a rejection."""
        rejections = ["no", "n", "nope", "cancel", "stop", "don't", "nevermind", "never mind", "abort"]
        words = text.split()
        return any(r in words or r == text for r in rejections)

    def _start_workflow(self, workflow: ToolWorkflow) -> str:
        """Start executing the workflow."""
        if not self.clean_tune_page:
            return "❌ System tools aren't connected. Cannot run tools."
        
        # Enable workflow mode
        self.clean_tune_page._in_workflow_mode = True
        self.current_workflow = workflow
        
        # Emit signal
        tool_names = [self.TOOL_DISPLAY_NAMES[t] for t in workflow.tools]
        self.tool_workflow_started.emit(tool_names)
        
        # Start first tool
        self._run_next_tool()
        
        return f"✅ Starting workflow with {len(workflow.tools)} tools. I'll update you as each completes."

    def _run_next_tool(self):
        """Run the next tool in the workflow."""
        if not self.current_workflow or self.current_workflow.is_complete():
            return
        
        tool = self.current_workflow.get_current_tool()
        if not tool:
            return
        
        tool_name = self.TOOL_DISPLAY_NAMES[tool]
        
        # Emit signal
        self.tool_started.emit(tool_name)
        
        # Execute the tool
        if hasattr(self.clean_tune_page, '_start_tool'):
            QTimer.singleShot(100, lambda: self._execute_tool(tool_name))

    def _execute_tool(self, tool_name: str):
        """Execute a specific tool and track its completion."""
        try:
            # Start the tool
            self.clean_tune_page._start_tool(tool_name)
            
            # Wait for log window to be created, then connect
            QTimer.singleShot(200, lambda: self._connect_to_log_window(tool_name))
                
        except Exception as e:
            self._on_tool_failed(tool_name, str(e))

    def _connect_to_log_window(self, tool_name: str):
        """Connect to the log window after it's been created."""
        try:
            log_window = getattr(self.clean_tune_page, '_active_log', None)
            
            if log_window:
                self._tool_windows[tool_name] = log_window
                
                # Connect to finished signal
                # The window now emits with ACTUAL status from detector
                log_window.finished.connect(
                    lambda success, msg, tn=tool_name: self._on_tool_finished(tn, success, msg)
                )
            else:
                self._on_tool_failed(tool_name, "Could not create tool window")
                
        except Exception as e:
            self._on_tool_failed(tool_name, f"Failed to connect to log window: {e}")

    def _on_tool_finished(self, tool_name: str, success: bool, message: str):
        """Called when a tool finishes - gets REAL status from detector."""
        if not self.current_workflow:
            return
        
        # Find the tool type
        tool_type = None
        for t, name in self.TOOL_DISPLAY_NAMES.items():
            if name == tool_name:
                tool_type = t
                break
        
        if tool_type:
            self.current_workflow.add_result(tool_type, success, message)
        
        # Emit signal with actual status
        self.tool_completed.emit(tool_name, success, message)
        
        # Advance workflow
        self.current_workflow.advance()
        
        # Check if workflow is complete
        if self.current_workflow.is_complete():
            # Small delay before showing summary
            QTimer.singleShot(1000, self._complete_workflow)
        else:
            # Small delay before starting next tool (let window close animation finish)
            QTimer.singleShot(1500, self._run_next_tool)

    def _on_tool_failed(self, tool_name: str, error: str):
        """Handle tool failure to start."""
        if not self.current_workflow:
            return
        
        tool_type = None
        for t, name in self.TOOL_DISPLAY_NAMES.items():
            if name == tool_name:
                tool_type = t
                break
        
        if tool_type:
            self.current_workflow.add_result(tool_type, False, error)
        
        self.tool_completed.emit(tool_name, False, error)
        self.current_workflow.advance()
        
        if self.current_workflow.is_complete():
            QTimer.singleShot(1000, self._complete_workflow)
        else:
            QTimer.singleShot(1500, self._run_next_tool)

    def _complete_workflow(self):
        """Called when all tools in workflow have completed."""
        if not self.current_workflow:
            return
        
        # Disable workflow mode
        if self.clean_tune_page:
            self.clean_tune_page._in_workflow_mode = False
        
        # Build summary report
        summary = self._build_workflow_summary(self.current_workflow)
        
        # Emit signal
        self.workflow_completed.emit(summary)
        
        # Clear workflow
        self.current_workflow = None
        self._tool_windows = {}

    def _build_workflow_summary(self, workflow: ToolWorkflow) -> str:
        """Build a summary report with actual results."""
        lines = [
            "## 📊 Maintenance Complete!\n",
            f"I've finished running {len(workflow.tools)} system maintenance tools. Here's what happened:\n"
        ]
        
        successful = 0
        failed = 0
        
        for result in workflow.results:
            tool_type = result['tool']
            success = result['success']
            message = result['message']
            tool_name = self.TOOL_DISPLAY_NAMES[tool_type]
            
            if success:
                successful += 1
                icon = "✅"
            else:
                failed += 1
                icon = "❌"
            
            # Show the actual message from the tool
            lines.append(f"{icon} **{tool_name}**: {message}")
        
        lines.append(f"\n**Summary**: {successful} successful, {failed} failed")
        
        if successful == len(workflow.tools):
            lines.append("\n🎉 All tools completed successfully! Your system should be running better now.")
        elif failed == len(workflow.tools):
            lines.append(
                "\n⚠️ All tools encountered issues. This could indicate a more serious system problem. "
                "You may want to check the Event Viewer (Reports tab) or seek professional help."
            )
        elif failed > 0:
            lines.append(
                f"\n⚠️ {failed} tool(s) had issues, but {successful} completed successfully. "
                "The issues have been noted above. You may need to investigate further or re-run specific tools."
            )
        
        if successful > 0:
            lines.append(
                "\n💡 **Recommendation**: Run maintenance tools like these regularly (weekly or monthly) "
                "to keep your system healthy."
            )
        
        return "\n".join(lines)