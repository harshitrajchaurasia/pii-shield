"""
PI Remover NER Module.

Contains the SpacyNER wrapper class for Named Entity Recognition.

Usage:
    from pi_remover.ner import SpacyNER, SPACY_AVAILABLE

    if SPACY_AVAILABLE:
        ner = SpacyNER(model_name="en_core_web_lg")
        if ner.load():
            entities = ner.extract_entities("John Smith works at Acme Corp.")
"""

import logging
from typing import List, Optional, Tuple


# Initialize logger
logger = logging.getLogger("pi_remover")


# spaCy Availability
# Try to import spaCy - graceful fallback if not available
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None  # type: ignore
    logger.warning("spaCy not installed. NER-based name detection disabled.")

# Import model manager for singleton model loading
try:
    from pi_remover.model_manager import SpacyModelManager, SPACY_AVAILABLE as MODEL_MANAGER_AVAILABLE
except ImportError:
    SpacyModelManager = None  # type: ignore
    MODEL_MANAGER_AVAILABLE = False


# spaCy NER Wrapper
class SpacyNER:
    """
    Wrapper for spaCy NER model.
    
    Uses SpacyModelManager singleton to share model instances across
    all PIRemover instances, preventing duplicate model loading.
    
    Supported entity types:
    - PERSON: People names
    - ORG: Organizations
    - GPE: Geopolitical entities (countries, cities, states)
    - LOC: Non-GPE locations (mountains, rivers, etc.)
    
    Example:
        >>> ner = SpacyNER()
        >>> ner.load()
        True
        >>> ner.extract_entities("John Smith works at Microsoft in Seattle.")
        [('John Smith', 'PERSON', 0, 10), ('Microsoft', 'ORG', 20, 29), ('Seattle', 'GPE', 33, 40)]
    """

    def __init__(self, model_name: str = "en_core_web_lg"):
        """
        Initialize SpacyNER wrapper.
        
        Args:
            model_name: Name of spaCy model to load.
                       Recommended: "en_core_web_lg" (accuracy) or "en_core_web_sm" (speed)
        """
        self.nlp = None
        self.model_name = model_name
        self._loaded = False

    def load(self) -> bool:
        """
        Load the spaCy model.
        
        Uses the singleton SpacyModelManager to share model instances
        across all PIRemover instances.
        
        Returns:
            True if model loaded successfully, False otherwise
        """
        if self._loaded:
            return True

        if not SPACY_AVAILABLE:
            logger.debug("spaCy not available, NER disabled")
            return False

        # Use singleton model manager if available
        if SpacyModelManager is not None:
            self.nlp = SpacyModelManager.get_model(self.model_name)
            if self.nlp is not None:
                self._loaded = True
                logger.info(f"Using shared spaCy model: {self.model_name}")
                return True
            else:
                logger.warning(f"SpacyModelManager failed to load '{self.model_name}'")
                return False
        
        # Fallback to direct loading (legacy behavior)
        if spacy is None:
            return False
            
        try:
            self.nlp = spacy.load(self.model_name)
            # Disable unnecessary pipeline components for speed
            try:
                self.nlp.disable_pipes(["parser", "lemmatizer"])
            except ValueError:
                pass  # Some models may not have these pipes
            self._loaded = True
            logger.info(f"Loaded spaCy model: {self.model_name}")
            return True
        except OSError:
            logger.warning(f"spaCy model '{self.model_name}' not found.")
            logger.info(f"Install with: python -m spacy download {self.model_name}")
            return False
        except Exception as e:
            logger.warning(f"Failed to load spaCy model '{self.model_name}': {e}")
            return False

    def extract_entities(
        self, 
        text: str,
        entity_types: Optional[List[str]] = None
    ) -> List[Tuple[str, str, int, int]]:
        """
        Extract named entities from text.
        
        Args:
            text: Input text to analyze
            entity_types: List of entity types to extract.
                         Default: ["PERSON", "ORG", "GPE", "LOC"]
        
        Returns:
            List of (text, label, start, end) tuples.
            Falls back to empty list on any error.
        """
        if not self._loaded or not text:
            return []

        if entity_types is None:
            entity_types = ["PERSON", "ORG", "GPE", "LOC"]

        try:
            doc = self.nlp(text)
            entities = []
            for ent in doc.ents:
                if ent.label_ in entity_types:
                    entities.append((ent.text, ent.label_, ent.start_char, ent.end_char))
            return entities
        except Exception as e:
            # Log but don't crash - return empty and let regex handle it
            logger.debug(f"NER extraction failed, falling back to regex: {e}")
            return []

    def extract_persons(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Extract only PERSON entities from text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of (name, start, end) tuples
        """
        entities = self.extract_entities(text, entity_types=["PERSON"])
        return [(ent[0], ent[2], ent[3]) for ent in entities]

    def extract_organizations(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Extract only ORG entities from text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of (org_name, start, end) tuples
        """
        entities = self.extract_entities(text, entity_types=["ORG"])
        return [(ent[0], ent[2], ent[3]) for ent in entities]

    def extract_locations(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Extract GPE and LOC entities from text.
        
        Args:
            text: Input text to analyze
            
        Returns:
            List of (location_name, start, end) tuples
        """
        entities = self.extract_entities(text, entity_types=["GPE", "LOC"])
        return [(ent[0], ent[2], ent[3]) for ent in entities]

    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready."""
        return self._loaded

    def __repr__(self) -> str:
        status = "loaded" if self._loaded else "not loaded"
        return f"SpacyNER(model='{self.model_name}', status='{status}')"


# Exports
__all__ = [
    'SpacyNER',
    'SPACY_AVAILABLE',
    'MODEL_MANAGER_AVAILABLE',
]
