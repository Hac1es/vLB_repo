from nicegui import ui

# Import pages để @ui.page được register
import pages.packages
import pages.package_form


ui.run(
    host="0.0.0.0",
    port=8081,
    title="Internal Repository",
    reload=True,
)
