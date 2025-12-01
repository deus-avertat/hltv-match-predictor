# 🧠 HLTV Match Predictor

A machine learning pipeline to **predict the winner of a Counter-Strike 2 match** based on match data 🎯  
This repository includes everything: scraping, feature engineering, model training, and a GUI for prediction.

This scraper currently works for HLTV as of **December 2025**. If HLTV ever updates I will try and make sure this script continues to work.

---

## 📁 Project Structure

```
github/
├── pipeline_gui.py               # Main pipeline script for predicting outcomes
│
├── model/
│   └── cs2_model.pkl             # Trained machine learning model
│
├── data/
│   ├── cache.db                  # Database of predicted matches (refreshes every 12 hours)
│   ├── hltv_data.json            # Team, map, and player data from the scraper.  
│   └── processed_matches.json    # List of matches already scraped (stops scraper from scraping the same match)
│
├── scraper/
│   └── scraping.py               # Script for scraping HLTV and outputting to a file to train on
│
├── trainer/
│   └── train.py                  # Script for training the model usingt the outputted scraper file.
│
├── utils/
│   └── database.py               # Stores helper functions for the database
│   └── dictionary.py             # Stores dictionary
│   └── driver.py                 # Stores helper functions for the UC driver
│   └── helpers.py                # Stores general helper functions
│
├── requirements.txt              # Project dependencies
└── README.md                     # Documentation (this file)
```

---

## ⚙️ How to Use

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Scrape match data**:
   - **NOTE:** You may need to supply your own cookies as sometimes Cloudflare will trigger bot activity, see `scraper/HELP.md` for instructions on getting cookies.
   ```bash
   python scraper/scraping.py
   ```


3. **Train the model**:
   ```bash
   python trainer/train.py
   ```

4. **Run predictions**:
   ```bash
   python src/prediction/predict.py
   ```

---

## 🧪 Technologies Used

- Python 🐍
- scikit-learn
- beautifulsoup4
- matplotlib, joblib
- undetectable chrome driver
- Custom data pipeline
- Web scraping

---

## 📊 What Does the Script Do?

- 🔍 Scrapes HTLV and generates a .json file ready for training.
- 🎓 Trains a machine learning model.
- 🧠 Predicts which team will win based on match features.

---

## 🧑‍💻 Authors

Originally created with by [@tatarenstas](https://github.com/tatarenstas)  
Forked and heavily modified by [@deus-avertat](https://github.com/deus-avertat)