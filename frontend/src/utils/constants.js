export const RISK_LEVELS = {
  INSIDER: 'insider',
  SUSPICIOUS: 'suspicious',
  CLEAN: 'clean',
}

export const DIRECTIONS = {
  YES: 'yes',
  NO: 'no',
}

export const FACTOR_LABELS = {
  entryTiming: 'Late Entry',
  marketCount: 'Few Markets',
  tradeSize: 'Large Bet',
  walletAge: 'New Wallet',
  concentration: 'Concentrated',
}

export const FACTOR_THRESHOLD = 0.6

export const KNOWN_WALLETS = {
  '0xee50a31c3f5a7c77824b12a941a54388a2827ed6': 'AlphaRaccoon',
  '0x6baf05d193692bb208d616709e27442c910a94c5': 'SBet365',
  '0x0afc7ce56285bde1fbe3a75efaffdfc86d6530b2': 'ricosuave',
  '0x7f1329ade2ec162c6f8791dad99125e0dc49801c': 'gj1',
  '0xc51eedc01790252d571648cb4abd8e9876de5202': 'hogriddahhhh',
  '0x976685b6e867a0400085b1273309e84cd0fc627c': 'fromagi',
  '0x55ea982cebff271722419595e0659ef297b48d7c': 'flaccidwillie',
}

export const POLYMARKET_URL_REGEX = /polymarket\.com\/(event|markets?)\//i
export const CONDITION_ID_REGEX = /^0x[0-9a-fA-F]{64}$/
export const TOKEN_ID_REGEX = /^\d{10,}$/

export const MOCK_CONDITION_IDS = {
  SPAIN_FIFA: '0xaabb1234cc5678dd9900aabb1234cc5678dd9900aabb1234cc5678dd9900aabb',
  MODI_ELECTION: '0xbbcc2345dd6789ee0011bbcc2345dd6789ee0011bbcc2345dd6789ee0011bbcc',
  MADURO_OUT: '0xccdd3456ee789ff1122ccdd3456ee789ff1122ccdd3456ee789ff1122ccdd34',
  TRUMP_PARDON: '0xddee4567ff8900112233ddee4567ff8900112233ddee4567ff8900112233ddee',
}
