from waitress import serve
import insights
serve(insights.app, host='0.0.0.0', port=8080, url_scheme='http')