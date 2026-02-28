from datetime import datetime, timezone
import math

def get_solar_longitude(dt=None):
    """
    Approximate solar longitude (lambda) in degrees.
    0 = Vernal Equinox, 90 = Summer Solstice, 180 = Autumnal Equinox, 270 = Winter Solstice.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    
    # Days since Vernal Equinox (~March 20/21)
    # Reference: 2025 Vernal Equinox was March 20 09:01 UTC
    reference_equinox = datetime(2025, 3, 20, 9, 1, tzinfo=timezone.utc)
    delta = dt - reference_equinox
    days = delta.total_seconds() / 86400
    
    # Approximate longitude change (360 degrees per 365.242 days)
    longitude = (days * 360 / 365.24219) % 360
    return longitude

def get_cosmic_phase_name(lon):
    if 0 <= lon < 15: return "♈ Spring Genesis (Vernal Equinox)"
    if 15 <= lon < 45: return "🌱 Growth (Mid-Spring)"
    if 45 <= lon < 75: return "☀️ Vitality (Late Spring)"
    if 75 <= lon < 105: return "♋ Peak Light (Summer Solstice)"
    if 105 <= lon < 135: return "🔥 Ripening (Mid-Summer)"
    if 135 <= lon < 165: return "🌾 Transition (Late Summer)"
    if 165 <= lon < 195: return "♎ Balance (Autumnal Equinox)"
    if 195 <= lon < 225: return "🍁 Harvesting (Mid-Autumn)"
    if 225 <= lon < 255: return "🌬️ Release (Late Autumn)"
    if 255 <= lon < 285: return "♑ Deep Stillness (Winter Solstice)"
    if 285 <= lon < 315: return "❄️ Preservation (Mid-Winter)"
    if 315 <= lon < 345: return "💧 Rebirth (Late Winter)"
    return "🌅 Renewal"

def get_cosmic_report():
    lon = get_solar_longitude()
    name = get_cosmic_phase_name(lon)
    return f"{name} (Solar Lon: {lon:.1f}°)"

if __name__ == "__main__":
    print(get_cosmic_report())
