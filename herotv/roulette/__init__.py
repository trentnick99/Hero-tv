"""Movie Roulette: the movie-guessing party game inside HERO TV.

It plays from HERO TV's own library (the media and art tables), so a film is known once, to both. The rules come from
the stand-alone Movie Roulette project: uniform random picks with repeat rules, a scene window that avoids the credits,
hints, a tie-aware scoreboard and score records that cannot be awarded twice.

  store    tables and the game settings
  pool     which films can come up, and the categories made from what HERO TV knows about them
  frames   choosing the moment and grabbing the picture (dark and flat pictures are thrown back)
  answers  is a typed guess the film?
  game     the game itself: rounds, guesses, hints, scores, history
  api      the /api/roulette/... requests
"""
