import os
from app import create_app

app = create_app(os.environ.get('FLASK_ENV', 'development'))

if __name__ == '__main__':
    app.run(debug=app.config.get('DEBUG', False), use_reloader=False, host='0.0.0.0', port=5000)
