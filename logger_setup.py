import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_structured_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    class MaskingJsonFormatter(jsonlogger.JsonFormatter):
        def process_log_record(self, log_record):
            import re
            message = str(log_record.get('message', ''))
            
            # Mask API keys and common sensitive keys if present in dictionaries or strings
            patterns = [
                (r'(["\']?(?:api[_\-]?key|token|password|secret)["\']?\s*[:=]\s*["\']?)([^"\',}\s]+)(["\']?)', r'\1***\3')
            ]
            for pattern, subst in patterns:
                message = re.sub(pattern, subst, message, flags=re.IGNORECASE)
                
            log_record['message'] = message
            return super().process_log_record(log_record)

    logHandler = logging.StreamHandler(sys.stdout)
    formatter = MaskingJsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%SZ'
    )
    logHandler.setFormatter(formatter)
    logger.addHandler(logHandler)
    return logger

logger = setup_structured_logging()
