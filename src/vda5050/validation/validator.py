import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import jsonschema
from jsonschema import ValidationError as JSONSchemaValidationError
from ..utils.exceptions import ValidationError as VDA5050ValidationError

logger = logging.getLogger(__name__)

class MessageValidator:
    """
    VDA5050 message validator using JSON Schema files.
    """
    
    def __init__(self, schema_dir: Optional[Path] = None):
        # Default to src/vda5050/validation/schemas
        self.schema_dir = schema_dir or Path(__file__).parent / "schemas"
        self._schema_cache: Dict[str, Dict] = {}
    
    def _load_schema(self, message_type: str) -> Dict[str, Any]:
        """Load and cache JSON schema for a message type."""
        if message_type not in self._schema_cache:
            schema_path = self.schema_dir / f"{message_type}.schema.json"
            if not schema_path.exists():
                raise VDA5050ValidationError(
                    f"Schema for '{message_type}' not found at {schema_path}"
                )
            with open(schema_path, 'r') as f:
                self._schema_cache[message_type] = json.load(f)
        return self._schema_cache[message_type]
    
    def validate_message(self, message_type: str, payload: str | dict) -> bool:
        """
        Validate a VDA5050 message against its JSON schema.
        
        Raises VDA5050ValidationError on JSON or schema validation failure.
        """
        try:
            schema = self._load_schema(message_type)
            data = json.loads(payload) if isinstance(payload, str) else payload
            jsonschema.validate(instance=data, schema=schema)
            logger.debug(f"Message '{message_type}' validation successful")
            return True
        except json.JSONDecodeError as e:
            raise VDA5050ValidationError(f"Invalid JSON for '{message_type}': {e}")
        except JSONSchemaValidationError as e:
            msg = f"Schema validation failed for '{message_type}': {e.message}"
            raise VDA5050ValidationError(msg)
    
    def get_schema(self, message_type: str) -> Dict[str, Any]:
        """Return the loaded JSON schema for a message type."""
        return self._load_schema(message_type)
    
    def get_required_fields(self, message_type: str) -> list[str]:
        """Return the list of required fields as declared in the schema."""
        schema = self._load_schema(message_type)
        return schema.get("required", [])
