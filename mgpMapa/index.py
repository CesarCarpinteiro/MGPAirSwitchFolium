from flask import Flask, render_template_string
import folium
import pandas as pd
from folium.plugins import Geocoder, TagFilterButton
from datetime import datetime
import locale
from dateutil.relativedelta import relativedelta

mgp = pd.read_csv('google_sheet_data.csv', sep=',', dtype={'Contacto': str})
# Assuming 'Data' column in mgp is a string, convert it to datetime format
mgp['Data'] = pd.to_datetime(mgp['Data'], format='%d/%m/%Y', errors='coerce').dt.date  # Converts and handles any errors if date format varies

mgp['Contacto'] = mgp['Contacto']
# Get the current date
current_date = datetime.now().date()

# Set locale to Portuguese (Brazil) for month names
#try:
#    locale.setlocale(locale.LC_TIME, 'pt_PT.UTF-8')
#except locale.Error:
#    print("Portuguese locale not available. Month names will appear in the default language.")

app = Flask(__name__)

@app.route("/")
def home():
    # Create a map centered around the mean location of the data
    m = folium.Map(location=[mgp['Latitude'].mean(), mgp['Longitude'].mean()], zoom_start=13)

    # Add points to the map
    for index, row in mgp.iterrows():
        # Calculate the number of months passed
        if pd.notnull(row['Data']):  # Check if the date is valid
           months_passed = (current_date.year - row['Data'].year) * 12 + (current_date.month - row['Data'].month)
        else:
           months_passed = 0  # Default value if 'Data' is not a valid date

        # Determine color based on the time passed
        if months_passed <= 8:
           color = 'gray'
           filterValue = 'Mais de 2 meses'
        elif 8 < months_passed <= 10:
           color = 'orange'
           filterValue = 'Menos de 2 meses'
        else:
           color = 'red'
           filterValue = 'Menos de 1 mês'
        
        # Format the original date for display
        display_date = row['Data'].strftime('%d/%m/%Y') if pd.notnull(row['Data']) else 'N/A'

        # Calculate next maintenance date, 12 months after 'Data'
        if pd.notnull(row['Data']):
           next_maintenance_date = row['Data'] + relativedelta(months=12)
           next_maintenance_display = next_maintenance_date.strftime('%d/%m/%Y') # e.g., "dezembro 2024"
        else:
           next_maintenance_display = 'N/A'

        # Create formatted popup text with larger font
        text = f"""
            <div style="font-size: 14px;">
                <p><strong>Cliente:</strong> {row.Cliente}</p>
                <p><strong>Contacto:</strong> {row.Contacto}</p>
                <p><strong>Nº Máquinas:</strong> {row.Num_Máquinas}, <strong>Marca:</strong> {row.Marca}</p>
                <p><strong>Data Instalação:</strong> {display_date}</p>
                <p><strong>Manutenção prevista:</strong> {next_maintenance_display}</p>
            </div>
        """
        folium.Marker( 
            location=[row['Latitude'], row['Longitude']],
            popup = folium.Popup(text, max_width = 700),
            icon=folium.Icon(color=color, icon='fan', prefix='fa'), tags=[filterValue]
        ).add_to(m)

    Geocoder().add_to(m)

    # Inject JavaScript to modify the Geocoder placeholder text
    
    TagFilterButton(['Mais de 2 meses', 'Menos de 2 meses', 'Menos de 1 mês'], name='Filter by Color').add_to(m)
    custom_js = """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        console.log("DOM fully loaded. Changing 'clear' button text...");

        // Locate the "clear" button in the header section
        var clearButton = document.querySelector('.tag-filter-tags-container ul.header li.ripple a');

        if (clearButton) {
            clearButton.textContent = 'Limpar'; // Update the text to 'Limpar'
            console.log("Changed 'clear' button to 'Limpar'");
        } else {
            console.error("Clear button not found.");
        }
    });
    document.addEventListener('DOMContentLoaded', function() {
        console.log("DOM fully loaded. Changing Geocoder placeholder text...");

        // Locate the search input field from the Geocoder
        var searchInput = document.querySelector('.leaflet-control-geocoder-form input');

        if (searchInput) {
            searchInput.setAttribute('placeholder', 'Pesquisar...'); // Update the placeholder text
            console.log("Changed Geocoder placeholder to 'Pesquisar'");
        } else {
            console.error("Geocoder search input not found.");
        }
    });
    </script>
    """
    
    m.get_root().html.add_child(folium.Element(custom_js))
    
    
    # Render the map
    m.get_root().render()
    header = m.get_root().header.render()
    body_html = m.get_root().html.render()
    script = m.get_root().script.render()

    return render_template_string(
        """
        <!DOCTYPE html>
        <html lang="pt">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>MGP Air Switch - Mapa de Serviços Executados</title>
                <style>
                    /* Global Styling */
                    body {
                        font-family: 'Arial', sans-serif;
                        margin: 0;
                        padding: 0;
                        background-color: #f4f4f9;
                    }

                    /* Header Styling */
                    h1 {
                        text-align: center;
                        margin-top: 50px;
                        font-size: 2.5em;
                        color: #333;
                        text-transform: none; /* No uppercase */
                        letter-spacing: 0px;
                        background-color: #4CAF50;
                        padding: 20px;
                        color: white;
                        border-radius: 8px;
                    }

                    .content-wrapper {
                        padding-bottom: 50px; /* Matches the footer height to prevent overlap */
                        min-height: 100vh; /* Ensures content wrapper covers full screen */
                        box-sizing: border-box;
                    }

                    .footer-spacer {
                        height: 35px; /* Same height as footer */
                    }
                    @media only screen and (max-width: 767px) {
                    .footer-spacer {
                        height: 20px;
                    }
                    }
                    /* General Map Container Styling */
                    .map-container {
                        width: 97%;
                        height: calc(100% - 180px);
                        border-radius: 10px;
                        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.1);
                        margin: 0 auto;
                    }

                    /* Responsive adjustments */
                    @media only screen and (max-width: 767px) {
                    .map-container {
                        height: calc(100% - 210px);
                    }
                    }

                    /* Footer Styling */
                    footer {
                        height: 50px; /* Fixed height */
                        text-align: center;
                        padding: 10px;
                        background-color: #333;
                        color: white;
                        width: 100%;
                        position: absolute; /* Sticky keeps it at the bottom when scrolling */
                        bottom: 0;
                    }
                </style>
                {{ header|safe }}
            </head>
            <body>
                <h1>MGP Air Switch - Mapa de Serviços Executados</h1>
                <div class="map-container">
                    {{ body_html|safe }}
                </div>
                <div class="footer-spacer"></div>
                <footer>
                    <p>&copy; MGP Air Switch</p>
                </footer>
                <script>
                    {{ script|safe }}
                </script>
            </body>
        </html>
        """,
        header=header,
        body_html=body_html,
        script=script,
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000, debug=True)