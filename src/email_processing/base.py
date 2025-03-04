from typing import Dict, Tuple, Optional, Any
from dataclasses import dataclass

@dataclass
class EmailAnalysisResult:
    """
    Structured result container for email analysis operations.
    
    Provides a standardized format for analysis results while maintaining
    flexibility for different analyzer implementations. Includes core fields
    for basic analysis as well as extensible fields for detailed results.

    Attributes:
        is_meeting (bool): Indicates if the email is meeting-related
        action_required (bool): Indicates if user action is needed
        relevant_data (Dict[str, str]): Extracted key information from email
        raw_content (str): Original email content for reference
        confidence (float): Confidence score of the analysis (0.0 to 1.0)
        analysis_details (Optional[Dict]): Additional analyzer-specific results
    """
    is_meeting: bool
    action_required: bool
    relevant_data: Dict[str, str]
    raw_content: str
    confidence: float = 0.0
    analysis_details: Optional[Dict[str, Any]] = None

class BaseEmailAnalyzer:
    """
    Base analyzer class defining the contract for email analysis implementations.
    
    Provides a standardized interface for email analysis operations while allowing
    specialized implementations to maintain their unique analysis capabilities.
    Includes utility methods for content validation and result formatting.
    """
    
    async def analyze_email(self, email_content: str) -> Tuple[str, Dict[str, Any]]:
        """
        Analyze email content and determine appropriate actions.
        
        This method defines the core contract that all analyzer implementations
        must follow. Implementations should process the email content and return
        a decision along with detailed analysis results.

        Args:
            email_content: Raw content of the email to analyze
            
        Returns:
            Tuple containing:
                - str: Decision string (e.g., "standard_response", "flag_for_action")
                - Dict[str, Any]: Analysis details including explanation and metadata
        
        Raises:
            NotImplementedError: Must be implemented by concrete analyzer classes
        """
        raise NotImplementedError("Must implement analyze_email")

    def _validate_email_content(self, content: str) -> bool:
        """
        Validate email content before analysis.
        
        Performs basic validation to ensure the content is suitable for analysis.
        Implementations may extend this with additional validation logic.

        Args:
            content: Email content to validate
            
        Returns:
            bool: True if content is valid for analysis, False otherwise
        """
        if not content:
            return False
        return bool(content.strip())

    def _format_analysis_result(
        self, 
        decision: str, 
        details: Dict[str, Any], 
        confidence: float = 0.0
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Format analysis results in a consistent structure.
        
        Standardizes the output format across different analyzer implementations
        while preserving all relevant analysis details and metadata.

        Args:
            decision: Analysis decision string
            details: Raw analysis details and metadata
            confidence: Confidence score for the analysis (0.0 to 1.0)
            
        Returns:
            Tuple containing formatted decision and analysis details with
            standardized structure for consistent handling downstream
        """
        return decision, {
            "explanation": details.get("explanation", ""),
            "confidence": confidence,
            "metadata": details.get("metadata", {}),
            "analysis_details": details
        }