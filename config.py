import os
from dotenv import load_dotenv

# Load environment variables from a .env file (optional)
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "sdkgnlsdfngsdlkjsklbnsdjbsnlkbn")
    BATCH_FILES_ROOT = os.environ.get('BATCH_FILES_ROOT', 'C:\\Working\\Automate\\PLM_Upload_Status')
    BATCH_OUTPUT_ROOT = os.environ.get('BATCH_OUTPUT_ROOT', 'C:\\Working\\Automate\\PLM_Upload_Status\\Tanishq_Batch_test\\output')  

class ProductionConfig(Config):
    PG_CREDENTIALS = {
        'hostname': os.environ.get("PG_HOSTNAME", "db.maximaapparel.com"),
        'port': os.environ.get("PG_PORT", "5432"),
        'maintenance_db': os.environ.get("PG_DATABASE", "maxima_reporting"),
        'username': os.environ.get("PG_USERNAME", "tswarnkar_mdio"),
        'password': os.environ.get("PG_PASSWORD", "TSwarnkar_Mdio@2025"),
        'schemas': {
            'test': {
                'name': 'test',
                'description': 'Test Environment Schema',
                'is_default': False
            },
            'public': {
                'name': 'public',
                'description': 'Public Schema',
                'is_default': True
            }
        },
        'default_schema': 'test',  # Set your default schema
        'pool_size': int(os.environ.get("PG_POOL_SIZE", "5")),
        'max_overflow': int(os.environ.get("PG_MAX_OVERFLOW", "10")),
        'pool_timeout': int(os.environ.get("PG_POOL_TIMEOUT", "30")),
        'pool_recycle': int(os.environ.get("PG_POOL_RECYCLE", "1800"))
    }

    # Helper method to get available schemas
    @staticmethod
    def get_available_schemas():
        return list(ProductionConfig.PG_CREDENTIALS['schemas'].keys())

    @staticmethod
    def get_default_schema():
        return ProductionConfig.PG_CREDENTIALS['default_schema']
