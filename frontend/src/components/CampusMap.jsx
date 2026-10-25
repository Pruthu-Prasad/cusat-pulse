import { useEffect, useMemo } from 'react'
import L from 'leaflet'
import { MapContainer, Marker, Polygon, Polyline, TileLayer, useMap, useMapEvents } from 'react-leaflet'
import { CATEGORY_COLORS } from '../api'
import { CAMPUS_RING } from '../campusBoundary'

const CAMPUS_BOUNDS = L.latLngBounds(CAMPUS_RING)
const WORLD = [[-85, -180], [-85, 180], [85, 180], [85, -180]]

// Dims everything outside the campus (the ring is a hole in a world-sized polygon), then outlines the campus.
// Neither layer is interactive, so taps still reach the map.
function CampusBoundary() {
  return (
    <>
      <Polygon positions={[WORLD, CAMPUS_RING]} interactive={false}
        pathOptions={{ stroke: false, fillColor: '#0f172a', fillOpacity: 0.28, fillRule: 'evenodd' }} />
      <Polygon positions={CAMPUS_RING} interactive={false}
        pathOptions={{ color: '#0d9488', weight: 3, opacity: 0.95, fillColor: '#14b8a6', fillOpacity: 0.07, lineJoin: 'round' }} />
    </>
  )
}

function pinIcon(issue) {
  const color = issue.status === 'RESOLVED' ? CATEGORY_COLORS.Resolved : CATEGORY_COLORS[issue.category] || '#6b7280'
  const multi = issue.unique_reporters > 1
  const cls = ['pin', multi && 'pin-pulse', issue.threat_level === 'Critical' && issue.status !== 'RESOLVED' && 'pin-flash'].filter(Boolean).join(' ')
  const badge = multi ? `<span class="pin-badge">${issue.unique_reporters} reports</span>` : ''
  return L.divIcon({
    className: '',
    html: `<div class="${cls}" style="background:${color};color:${color}">${badge}</div>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  })
}

export const CAMPUS_CENTER = [CAMPUS_BOUNDS.getCenter().lat, CAMPUS_BOUNDS.getCenter().lng]

const dropIcon = L.divIcon({ className: '', html: '<div class="pin-new"></div>', iconSize: [26, 26], iconAnchor: [13, 26] })

function ClickHandler({ onPick }) {
  useMapEvents({ click: (e) => onPick?.({ lat: e.latlng.lat, lng: e.latlng.lng }) })
  return null
}

function FlyTo({ target }) {
  const map = useMap()
  useEffect(() => { if (target) map.flyTo([target.lat, target.lng], Math.max(map.getZoom(), 18), { duration: 0.6 }) }, [target, map])
  return null
}

function InvalidateOnResize() {
  const map = useMap()
  useEffect(() => {
    const ro = new ResizeObserver(() => map.invalidateSize())
    ro.observe(map.getContainer())
    return () => ro.disconnect()
  }, [map])
  return null
}

function HeatLayer({ points }) {
  const map = useMap()
  useEffect(() => {
    let layer
    let cancelled = false
    window.L = L // leaflet.heat attaches to the global L
    import('leaflet.heat').then(() => {
      if (cancelled) return
      layer = L.heatLayer(points.map((p) => [p.lat, p.lng, Math.max(0.15, p.weight)]), { radius: 50, blur: 30, maxZoom: 16, max: 0.7, minOpacity: 0.35 })
      layer.addTo(map)
    })
    return () => { cancelled = true; if (layer) map.removeLayer(layer) }
  }, [points, map])
  return null
}

export default function CampusMap({ issues = [], links = [], pin, onPick, onIssueClick, heatPoints, showPins = true, dark, flyTo, className = '' }) {
  const byId = useMemo(() => Object.fromEntries(issues.map((i) => [i.id, i])), [issues])
  // CARTO basemaps now need an API key, so we use OSM tiles and darken them with a CSS filter.
  return (
    <MapContainer bounds={CAMPUS_BOUNDS} boundsOptions={{ padding: [20, 20] }} maxBounds={CAMPUS_BOUNDS.pad(1.2)} maxBoundsViscosity={0.8}
      minZoom={14} className={`h-full w-full ${dark ? 'map-dark' : ''} ${className}`} zoomControl={false}>
      <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" maxZoom={19}
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
      <CampusBoundary />
      <InvalidateOnResize />
      <ClickHandler onPick={onPick} />
      <FlyTo target={flyTo} />
      {heatPoints && <HeatLayer points={heatPoints} />}
      {showPins && issues.map((i) => (
        <Marker key={i.id} position={[i.lat, i.lng]} icon={pinIcon(i)} eventHandlers={{ click: () => onIssueClick?.(i) }} />
      ))}
      {showPins && links.map((l, n) => byId[l.issue_a] && byId[l.issue_b] && (
        <Polyline key={n} positions={[[byId[l.issue_a].lat, byId[l.issue_a].lng], [byId[l.issue_b].lat, byId[l.issue_b].lng]]}
          pathOptions={{ color: '#0d9488', dashArray: '6 8', weight: 3 }} />
      ))}
      {pin && <Marker position={[pin.lat, pin.lng]} icon={dropIcon} />}
    </MapContainer>
  )
}
