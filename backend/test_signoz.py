from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry import trace
import time

exporter = OTLPSpanExporter(
    endpoint="https://ingest.us2.signoz.cloud:443",
    headers={"signoz-ingestion-key": "G9N8aDuKxOQxltq2tdIF4cMh6-Vfn3QoCk1y"},
    insecure=False,
)

provider = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(exporter))
trace.set_tracer_provider(provider)

tracer = trace.get_tracer("test")
with tracer.start_as_current_span("test.connectivity") as span:
    span.set_attribute("test.key", "hello_signoz")
    time.sleep(0.1)

provider.force_flush()
print("Done — check SigNoz in 30 seconds")