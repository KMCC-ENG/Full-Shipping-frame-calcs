# Engineering Calculators

One Streamlit app opens on a homepage with three choices.

| Calculator | What it calculates |
| --- | --- |
| Coil Center of Gravity | Assembly weight and longitudinal center of gravity from tube and component weights. |
| Tube Load Analyzer | Support reactions, bending moment, shear, deflection and nominal stress for a tube with two fixed supports. |
| Shipping Frame Load Analyzer | The response of a lifting frame with beam layers, coils, rods, lifting points and applied loads. |

Select a card to open a calculator. Select **← Home** to return. Each calculator keeps its own dimensions, loads and settings in the current browser session, including partially entered models. Home works before running a calculation. Refreshing the browser, closing the session or restarting the server can clear session inputs. The shipping frame calculator also supports saving and loading a design as JSON.

## Run on your computer

Extract the entire ZIP. From the folder containing `app.py`, run these commands with Python 3.11 or newer. Install the dependencies once per environment.

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows, you can also double-click `run_app.bat` after installing the dependencies. Keep the terminal open while using the app.

## Run on Streamlit Community Cloud

Upload the contents of the extracted folder to your GitHub repository, preserving the `assets` and `.streamlit` folders. Select **app.py** as the main file when deploying from the repository root. The full dependency list is in `requirements.txt`.

## Calculator guides

- [Coil Center of Gravity](docs/coil_cg.md)
- [Tube Load Analyzer](docs/tube_load.md)
- [Shipping Frame Load Analyzer](docs/shipping_frame.md)

The `examples` folder contains editable shipping frame designs. The `verification` folder contains records supplied with the original frame solver.

## Run the tests

```sh
python -m pip install pytest
python -m pytest tests
```

The section sketcher also has a JavaScript test suite. To run it, use `npm install` followed by `npm test` inside `tests`. Node.js is only needed for that test suite.
