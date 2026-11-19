// Chart colours and ink, from the validated reference palette (light mode; the app is light-only).
//
// Status -> categorical slot, in STATUS_ORDER (the stacking order). Hues echo the status badges
// used elsewhere (approved green, pending amber, rejected red) and the order keeps every
// adjacent pair distinguishable under colour-vision deficiency (validator: worst adjacent CVD
// dE 16.2, normal-vision dE 30.3). Yellow is under 3:1 on the surface, so every chart also
// offers a table view and a legend (identity never relies on colour alone).

export const STATUS_ORDER = ['APPROVED', 'PENDING', 'CANCELLED', 'REJECTED', 'EXPIRED'];

export const STATUS_COLORS = {
  APPROVED: '#008300',
  PENDING: '#eda100',
  CANCELLED: '#2a78d6',
  REJECTED: '#e34948',
  EXPIRED: '#6250d6',
};

export const INK = {
  primary: '#0b0b0b',
  secondary: '#52514e',
  muted: '#898781',
  grid: '#e1e0d9',
  axis: '#c3c2b7',
  surface: '#ffffff',
};
