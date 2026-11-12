const AMENITY_LABELS: Record<string, string> = {
  WIFI: 'Wi-Fi',
  POOL: 'Pool',
  GYM: 'Gym',
  BREAKFAST: 'Breakfast',
  PARKING: 'Parking',
  SPA: 'Spa',
  PET_FRIENDLY: 'Pet-friendly',
  AIR_CONDITIONING: 'A/C',
  RESTAURANT: 'Restaurant',
  SHUTTLE: 'Shuttle',
}

export function amenityLabel(amenity: string): string {
  return AMENITY_LABELS[amenity] ?? amenity
}
