import type { HotelEntry } from '../types'
import { DetailsDialog, PolicyDialog } from './Dialogs'

export type DialogState =
  { kind: 'details'; entry: HotelEntry } | { kind: 'policy'; hotelId: string } | null

export function ActiveDialog({ dialog, onClose }: { dialog: DialogState; onClose: () => void }) {
  if (dialog?.kind === 'details') {
    return (
      <DetailsDialog key={dialog.entry.hotel.hotel_id} entry={dialog.entry} onClose={onClose} />
    )
  }
  if (dialog?.kind === 'policy') {
    return <PolicyDialog key={dialog.hotelId} hotelId={dialog.hotelId} onClose={onClose} />
  }
  return null
}
