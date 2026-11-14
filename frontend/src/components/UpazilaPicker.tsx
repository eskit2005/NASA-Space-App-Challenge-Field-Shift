import { useState, useMemo } from 'react';
import upazilasData from '../data/upazilas.json';
import type { UpazilaPlace } from '../types/api';

interface UpazilaPickerProps {
  selectedUpazila: string;
  selectedDistrict: string;
  latitude: string;
  longitude: string;
  onSelectPlace: (place: UpazilaPlace) => void;
  onChangeManualCoords: (lat: string, lon: string) => void;
}

export default function UpazilaPicker({
  selectedUpazila,
  selectedDistrict,
  latitude,
  longitude,
  onSelectPlace,
  onChangeManualCoords,
}: UpazilaPickerProps) {
  const [query, setQuery] = useState(
    selectedUpazila ? `${selectedUpazila}, ${selectedDistrict}` : ''
  );
  const [isOpen, setIsOpen] = useState(false);
  const [manualMode, setManualMode] = useState(false);

  const places: UpazilaPlace[] = useMemo(() => {
    return (upazilasData as { places: UpazilaPlace[] }).places || [];
  }, []);

  const filteredPlaces = useMemo(() => {
    if (!query.trim()) {
      // return 6 default popular agricultural upazilas
      return places.slice(0, 8);
    }
    const q = query.toLowerCase().trim();
    // Normalize common English spelling variations for Bangladesh administrative areas
    const normalizedQ = q
      .replace(/\bbogra\b/g, 'bogura')
      .replace(/\bbarisal\b/g, 'barishal')
      .replace(/\bchittagong\b/g, 'chattogram')
      .replace(/\bcomilla\b/g, 'cumilla')
      .replace(/\bjessore\b/g, 'jashore');

    return places
      .filter(p => {
        const u = p.upazila.toLowerCase();
        const d = p.district.toLowerCase();
        const div = p.division.toLowerCase();
        return (
          u.includes(q) || d.includes(q) || div.includes(q) ||
          u.includes(normalizedQ) || d.includes(normalizedQ) || div.includes(normalizedQ)
        );
      })
      .slice(0, 10);
  }, [places, query]);

  function handleSelect(place: UpazilaPlace) {
    setQuery(`${place.upazila}, ${place.district}`);
    setIsOpen(false);
    onSelectPlace(place);
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <label style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--stone-700)' }}>
            Search Bangladesh Upazila / District
          </label>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => setManualMode(!manualMode)}
            style={{ fontSize: '0.75rem', padding: '2px 8px' }}
          >
            {manualMode ? '← Search by Name' : 'Enter GPS Manually →'}
          </button>
        </div>

        {!manualMode ? (
          <div style={{ position: 'relative' }}>
            <input
              type="text"
              value={query}
              onChange={e => {
                setQuery(e.target.value);
                setIsOpen(true);
              }}
              onFocus={() => setIsOpen(true)}
              placeholder="Type upazila or district (e.g. Raninagar, Naogaon, Bogura...)"
              style={{ paddingLeft: 38 }}
            />
            <span style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', fontSize: 16 }}>
              🔍
            </span>

            {/* Dropdown list */}
            {isOpen && (
              <div
                style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  background: 'white',
                  borderRadius: 'var(--radius-md)',
                  boxShadow: 'var(--shadow-lg)',
                  border: '1px solid var(--stone-200)',
                  marginTop: 4,
                  maxHeight: 240,
                  overflowY: 'auto',
                  zIndex: 50,
                }}
              >
                {filteredPlaces.length === 0 ? (
                  <div style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--stone-400)' }}>
                    No matching upazila found. Try checking spelling or enter coordinates manually.
                  </div>
                ) : (
                  filteredPlaces.map(place => (
                    <div
                      key={place.code}
                      onClick={() => handleSelect(place)}
                      style={{
                        padding: '10px 14px',
                        borderBottom: '1px solid var(--stone-100)',
                        cursor: 'pointer',
                        fontSize: '0.875rem',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        transition: 'background 0.15s',
                      }}
                      onMouseEnter={e => (e.currentTarget.style.background = 'var(--green-50)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'white')}
                    >
                      <div>
                        <strong>{place.upazila}</strong>
                        <span style={{ color: 'var(--stone-500)', marginLeft: 6 }}>
                          ({place.district}, {place.division})
                        </span>
                      </div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--stone-400)', fontFamily: 'monospace' }}>
                        {place.latitude.toFixed(2)}°N, {place.longitude.toFixed(2)}°E
                      </span>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 10, animation: 'fadeIn 0.2s' }}>
            <div style={{ flex: 1 }}>
              <input
                type="number"
                step="any"
                placeholder="Latitude (e.g. 23.8103)"
                value={latitude}
                onChange={e => onChangeManualCoords(e.target.value, longitude)}
              />
            </div>
            <div style={{ flex: 1 }}>
              <input
                type="number"
                step="any"
                placeholder="Longitude (e.g. 90.4125)"
                value={longitude}
                onChange={e => onChangeManualCoords(latitude, e.target.value)}
              />
            </div>
          </div>
        )}

        {/* Selected location indicator badge */}
        {latitude && longitude && (
          <div style={{
            marginTop: 10,
            background: 'var(--green-50)',
            border: '1px solid var(--green-200)',
            borderRadius: 8,
            padding: '8px 12px',
            fontSize: '0.82rem',
            color: 'var(--green-800)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}>
            <span>
              📍 <strong>{selectedUpazila ? `${selectedUpazila}, ${selectedDistrict}` : 'Custom Location'}</strong>
              <span style={{ color: 'var(--stone-500)', marginLeft: 6 }}>
                ({parseFloat(latitude).toFixed(4)}°N, {parseFloat(longitude).toFixed(4)}°E)
              </span>
            </span>
            <span className="badge badge-green">Ready</span>
          </div>
        )}
      </div>
    </div>
  );
}
