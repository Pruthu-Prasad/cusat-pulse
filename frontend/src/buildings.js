// CUSAT Thrikkakara campus places, from OpenStreetMap (© OpenStreetMap contributors, ODbL).
// `quick` ones show as chips on the student map; the rest are in the "All buildings" picker.
export const BUILDINGS = [
  // Hostels
  { name: 'Sahara Hostel', group: 'Hostels', lat: 10.04589, lng: 76.32927, quick: true },
  { name: 'Sarovar Hostel', group: 'Hostels', lat: 10.04663, lng: 76.3299, quick: true },
  { name: 'Swaraj Hostel', group: 'Hostels', lat: 10.04624, lng: 76.33085 },
  { name: 'Sagar Hostel', group: 'Hostels', lat: 10.04614, lng: 76.33108 },
  { name: 'Siberia Hostel', group: 'Hostels', lat: 10.04729, lng: 76.33024 },
  { name: 'Athulya Hostel', group: 'Hostels', lat: 10.04455, lng: 76.32384, quick: true },
  { name: 'Aishwarya Hostel', group: 'Hostels', lat: 10.04394, lng: 76.32384, quick: true },
  { name: 'Anaswara Hostel', group: 'Hostels', lat: 10.0434, lng: 76.32378 },
  { name: 'Anakha Hostel', group: 'Hostels', lat: 10.04527, lng: 76.32425 },
  { name: 'Sanathana Hostel', group: 'Hostels', lat: 10.04102, lng: 76.32723 },
  { name: 'Sahrudaya Hostel', group: 'Hostels', lat: 10.03994, lng: 76.32864 },
  { name: 'International Students Hostel', group: 'Hostels', lat: 10.03971, lng: 76.32804 },
  { name: 'Sarovar Mess', group: 'Hostels', lat: 10.04657, lng: 76.33023 },

  // School of Engineering
  { name: 'SOE', full: 'School of Engineering', group: 'School of Engineering', lat: 10.04878, lng: 76.33132, quick: true },
  { name: 'SOE A Block', group: 'School of Engineering', lat: 10.04856, lng: 76.33157 },
  { name: 'SOE C Block', group: 'School of Engineering', lat: 10.04917, lng: 76.33247 },
  { name: 'SOE Software Block', group: 'School of Engineering', lat: 10.04927, lng: 76.33135 },
  { name: 'SOE New Laboratory Block', group: 'School of Engineering', lat: 10.04979, lng: 76.33141 },
  { name: 'SOE Office', group: 'School of Engineering', lat: 10.04829, lng: 76.3315 },
  { name: 'SOE Canteen', group: 'School of Engineering', lat: 10.04787, lng: 76.3319 },
  { name: 'Dept. of Electrical & Electronics Engg.', group: 'School of Engineering', lat: 10.04765, lng: 76.33104 },
  { name: 'Division of Safety & Fire Engg.', group: 'School of Engineering', lat: 10.0478, lng: 76.33086 },
  { name: 'Fluid Mechanics Lab', group: 'School of Engineering', lat: 10.04748, lng: 76.33148 },
  { name: 'Thermal Engineering Lab', group: 'School of Engineering', lat: 10.0476, lng: 76.33131 },
  { name: 'Fire and Safety Ground', group: 'School of Engineering', lat: 10.04802, lng: 76.33032 },
  { name: 'Kunjali Marakkar School of Marine Engg.', full: 'Kunjali Marakkar School of Marine Engineering (KMSME)', group: 'School of Engineering', lat: 10.04105, lng: 76.32984 },

  // Departments and schools
  { name: 'Dept. of Computer Applications', full: 'Department of Computer Applications (DCA)', group: 'Departments', lat: 10.04614, lng: 76.32614 },
  { name: 'Dept. of Electronics', group: 'Departments', lat: 10.04528, lng: 76.32542 },
  { name: 'Dept. of Ship Technology', group: 'Departments', lat: 10.04527, lng: 76.32617 },
  { name: 'Ship Technology Lab', group: 'Departments', lat: 10.04573, lng: 76.326 },
  { name: 'Dept. of Polymer Science & Rubber Tech.', full: 'Department of Polymer Science and Rubber Technology (PS&RT)', group: 'Departments', lat: 10.04617, lng: 76.32553 },
  { name: 'Dept. of Physics', full: 'Department of Physics & Applied Chemistry block', group: 'Departments', lat: 10.04429, lng: 76.32708 },
  { name: 'Dept. of Applied Chemistry', group: 'Departments', lat: 10.04417, lng: 76.32718 },
  { name: 'Dept. of Instrumentation', group: 'Departments', lat: 10.04472, lng: 76.32707 },
  { name: 'Dept. of Biotechnology', group: 'Departments', lat: 10.04473, lng: 76.32756 },
  { name: 'Dept. of Mathematics', group: 'Departments', lat: 10.04363, lng: 76.32725 },
  { name: 'Dept. of Statistics & Foreign Languages', full: 'Department of Statistics, Department of Foreign Languages', group: 'Departments', lat: 10.04312, lng: 76.328 },
  { name: 'Dept. of Hindi', group: 'Departments', lat: 10.04272, lng: 76.32805 },
  { name: 'School of Legal Studies', full: 'School of Legal Studies (SLS)', group: 'Departments', lat: 10.04388, lng: 76.32782 },
  { name: 'School of Management Studies', full: 'School of Management Studies (SMS)', group: 'Departments', lat: 10.043, lng: 76.32761 },
  { name: 'School of Environmental Studies', group: 'Departments', lat: 10.04564, lng: 76.32674 },
  { name: 'International School of Photonics', full: 'International School of Photonics (ISP)', group: 'Departments', lat: 10.04444, lng: 76.32566 },
  { name: 'Inter University Centre for IPR Studies', full: 'Inter University Centre for IPR Studies (IUCIPRS)', group: 'Departments', lat: 10.04391, lng: 76.32855 },
  { name: 'Centre for Budget Studies', group: 'Departments', lat: 10.04573, lng: 76.32722 },
  { name: 'Interdisciplinary Centre for Research Ethics', group: 'Departments', lat: 10.04437, lng: 76.32744 },
  { name: 'Thin Film Microelectronics Lab', group: 'Departments', lat: 10.0443, lng: 76.32698 },
  { name: 'Dream Lab', group: 'Departments', lat: 10.04421, lng: 76.3268 },
  { name: 'Small Animal Housing Facility', group: 'Departments', lat: 10.04452, lng: 76.32718 },
  { name: 'PSRT Lab', group: 'Departments', lat: 10.04573, lng: 76.32564 },
  { name: 'ACARR Radar Centre', full: 'Advanced Centre for Atmospheric Radar Research', group: 'Departments', lat: 10.04262, lng: 76.33212 },

  // Library, halls and admin
  { name: 'CITTIC', full: 'Centre for Innovation, Technology Transfer and Industrial Collaboration', group: 'Admin & services', lat: 10.04101, lng: 76.32825, quick: true },
  { name: 'University Library', full: 'Central Library', group: 'Admin & services', lat: 10.04426, lng: 76.3252, quick: true },
  { name: 'University Library Old Block', group: 'Admin & services', lat: 10.04456, lng: 76.32518 },
  { name: 'Seminar Complex', group: 'Admin & services', lat: 10.04372, lng: 76.32486 },
  { name: 'Seminar Hall', group: 'Admin & services', lat: 10.04418, lng: 76.32739 },
  { name: 'PSRT Auditorium', group: 'Admin & services', lat: 10.0462, lng: 76.32534 },
  { name: 'PSRT Library', group: 'Admin & services', lat: 10.04612, lng: 76.32549 },
  { name: 'Open Air Auditorium', group: 'Admin & services', lat: 10.04191, lng: 76.32765 },
  { name: 'Administrative Office', full: 'Administrative Office (ADM)', group: 'Admin & services', lat: 10.04285, lng: 76.32437 },
  { name: 'CIRM', full: 'Centre for Information Resource Management', group: 'Admin & services', lat: 10.04574, lng: 76.3249 },
  { name: 'Engineering Works Department', group: 'Admin & services', lat: 10.04366, lng: 76.32541 },
  { name: 'Electrical Workshop', group: 'Admin & services', lat: 10.04627, lng: 76.32654 },
  { name: 'Guest House', full: 'University Guest House & Visiting Faculty Complex', group: 'Admin & services', lat: 10.04364, lng: 76.32573 },
  { name: 'Medical Centre', group: 'Admin & services', lat: 10.04282, lng: 76.32872 },
  { name: 'Post Office', group: 'Admin & services', lat: 10.04306, lng: 76.32867 },
  { name: 'SBI ATM', group: 'Admin & services', lat: 10.04198, lng: 76.32846 },
  { name: 'Daycare', group: 'Admin & services', lat: 10.04198, lng: 76.3287 },
  { name: 'Security Gate', group: 'Admin & services', lat: 10.04385, lng: 76.32607 },
  { name: 'Water Authority Building', group: 'Admin & services', lat: 10.04695, lng: 76.33129 },
  { name: 'Staff Quarters', group: 'Admin & services', lat: 10.04126, lng: 76.32847 },

  // Food
  { name: 'Amenity Centre', full: 'Student Amenity Centre: medical clinic, student union, hostel office', group: 'Food & shops', lat: 10.04261, lng: 76.32882, quick: true },
  { name: 'CUSAT Restaurant', group: 'Food & shops', lat: 10.04219, lng: 76.32857 },
  { name: 'Admin Canteen', group: 'Food & shops', lat: 10.04249, lng: 76.32456 },
  { name: 'CUSAT Cafe', group: 'Food & shops', lat: 10.04307, lng: 76.32529 },
  { name: 'Milma Booth', group: 'Food & shops', lat: 10.0416, lng: 76.32869 },

  // Sports and open spaces
  { name: 'New Indoor Stadium', group: 'Sports & grounds', lat: 10.04377, lng: 76.32909 },
  { name: 'CUSAT Arena', group: 'Sports & grounds', lat: 10.04315, lng: 76.32912 },
  { name: 'University Ground', group: 'Sports & grounds', lat: 10.04006, lng: 76.32719 },
  { name: 'Indoor Badminton Court', group: 'Sports & grounds', lat: 10.04067, lng: 76.3266 },
  { name: 'Volleyball Court', group: 'Sports & grounds', lat: 10.04214, lng: 76.32903 },
  { name: 'Swaraj Hostel Pitch', group: 'Sports & grounds', lat: 10.04637, lng: 76.33054 },
  { name: 'University Park', group: 'Sports & grounds', lat: 10.04419, lng: 76.3246 },
  { name: 'Butterfly Park', group: 'Sports & grounds', lat: 10.04324, lng: 76.32557 },
  { name: 'Momentum Park', group: 'Sports & grounds', lat: 10.04572, lng: 76.32624 },
  { name: "Lover's Triangle", group: 'Sports & grounds', lat: 10.04211, lng: 76.32809 },
  { name: 'Children\'s Science Park', full: 'Centre for Science in Society (C-SiS)', group: 'Sports & grounds', lat: 10.04619, lng: 76.32784 },
  { name: 'CUSAT Pond', group: 'Sports & grounds', lat: 10.04509, lng: 76.3288 },
]

export const GROUPS = [...new Set(BUILDINGS.map((b) => b.group))]
export const QUICK = BUILDINGS.filter((b) => b.quick)

const SNAP_METERS = 40

function meters(a, b) {
  const r = 6371000, rad = Math.PI / 180
  const dLat = (b.lat - a.lat) * rad, dLng = (b.lng - a.lng) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2
  return 2 * r * Math.asin(Math.sqrt(h))
}

// Nearest named building to a tapped point, if the tap is close enough to count as "in" it.
export function nearestBuilding(p) {
  let best = null, dist = Infinity
  for (const b of BUILDINGS) {
    const d = meters(p, b)
    if (d < dist) { best = b; dist = d }
  }
  return dist <= SNAP_METERS ? best : null
}
