NeuroSync EEG Training — Quick Start
=====================================

Prerequisites (Mac):
  pip install muselsl pylsl scikit-learn joblib numpy scipy

Step 1: Start Muse stream
  muselsl stream --address XX:XX:XX:XX:XX:XX
  (replace with your Muse BLE address — find it with: muselsl list)

Step 2: Run training GUI (separate terminal)
  python scripts/training/train_gui.py

Step 3: Follow GUI instructions (~12 minutes)
  - Settle (30s): relax
  - DISENGAGED (90s x2): stare at dot, do nothing
  - FOCUSED (90s x2): Stroop test — say the COLOR not the word
  - OVERLOADED (90s x2): N-back — press SPACE when letter matches N ago

Step 4: Model saved automatically
  config/backend/classifier.joblib

Step 5: Restart the backend
  The main app loads the model on startup automatically.
  No code changes needed.

Tips:
  - Sit still, minimize jaw movement during recording
  - For DISENGAGED: truly do nothing, let mind wander
  - For OVERLOADED: try hard on the N-back — don't give up
  - For FOCUSED: say each color out loud clearly
