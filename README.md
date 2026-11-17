# Engineering Calculators

Engineering Calculators brings three tools into one application for reviewing the weight, loading and handling of tube and coil assemblies. It gives engineering users one place to open the appropriate tool, enter a model, inspect its visual representation and return to their work as they move between related tasks.

The application opens on a homepage with three choices, **Coil Center of Gravity**, **Tube Load Analyzer** and **Shipping Frame Load Analyzer**. Each calculator has its own inputs and working model. A **← Home** button returns to the homepage while retaining the user's entries in the current session.

## Purpose and intended audience

The app supports the practical work that surrounds manufacturing, assembly, handling and shipping of tubular products. Its intended users include engineering technologists, mechanical engineers, manufacturing personnel and reviewers who have the dimensions, weights and arrangement details needed to describe a particular job.

A user may need to understand where an assembly balances, investigate a tube under a particular support arrangement, or develop a shipping frame around a group of coils. These activities often arise during the same project. Bringing the tools together makes it easier to move through that work with a consistent interface and fewer repeated entries.

The intended outcome is a clearly defined engineering case that can be reviewed, revised and discussed. The user supplies the project information and chooses the model appropriate to the physical arrangement. The app organizes that information and provides results for that case. Engineering decisions still depend on the accuracy of the inputs and the suitability of the selected assumptions.

## Main objectives

### Provide one starting point for three engineering tasks

The homepage gives users a direct choice based on their immediate objective. Each card opens its calculator within the same application and browser tab. This makes the app suitable for a work session that includes several related questions about the same assembly or manufacturing job.

The calculator names identify the task being performed. The **← Home** button occupies a consistent location, so users can return to the starting point without searching through input tabs or closing their work.

### Preserve work during navigation

Users should be able to pause a model, look at another tool and return to their existing entries. Dimensions, component lists, loads and settings belong to the current working session. Partially completed entries can also be retained while the user gathers missing information.

This objective is particularly useful when a frame model contains several layers, coils and rods, or when the tube and center-of-gravity tools contain multiple additional loads or components. Returning Home is a navigation action. The existing Reset, removal and example-loading controls provide the actions that deliberately change a model.

### Keep each calculator's data independent

Every calculator owns its own inputs. Editing a length, weight or material setting in one tool affects that tool's model. The user can therefore investigate different cases in the three calculators during the same session.

For example, a user can enter a 300 in tube in Tube Load Analyzer and a 120 in assembly in Coil Center of Gravity. Returning to either calculator retrieves its own length and component entries. When a value from one analysis is relevant to another, the user chooses the value and enters it into the receiving calculator.

### Make the entered arrangement easy to review

The visual views help users check whether their inputs represent the intended assembly. Component positions, loading locations and section details can be reviewed alongside their numeric entries. This supports finding input mistakes early and explaining a case to someone who did not enter it.

Meaningful component names and consistent position references make that review more effective. The goal is for a reviewer to understand what was modeled, which values were supplied and what question the user intended to answer.

### Support deliberate design revisions

The tools make it practical to revise an arrangement and inspect the effect of that change. Users can edit geometry, reposition a component, change a load or refine a frame layout while keeping the rest of the case organized.

A useful comparison starts with a defined baseline and a clear reason for the revision. Recording the relevant inputs and exporting the available results provides a way to compare the two cases after the working model has been edited.

### Help users communicate their findings

The app presents a combination of diagrams, numeric results and downloadable data. These outputs support engineering discussions, internal reviews and preparation of project records. The available CSV exports allow users to bring selected results into spreadsheets or other reporting work.

Shipping frame designs can also be saved as JSON files and loaded for subsequent editing. This supports continuing work on a frame or passing its input model to another user of the app.

## Coil Center of Gravity

The objective of Coil Center of Gravity is to establish the longitudinal balance location of an assembly represented by a straight reference tube and additional component weights. It is useful when the weight distribution includes fittings or other parts whose centers lie away from the main tube's midpoint.

The user can describe added parts individually, give them meaningful names and place them at their own center-of-gravity positions. Positions may extend beyond the reference tube's ends. A component distributed over a length can be represented over its specified interval.

Typical reasons for using this tool include the following.

- Prepare the weight and balance information for a tube or coil assembly.
- Review how adding or repositioning a fitting changes the assembly's balance location.
- Check that all relevant component weights have been included in the case.
- Compare the modeled balance location with the locations being considered for handling or support.
- Export an organized component list and the resulting assembly summary for review.

For example, a fitting may project beyond the end of a tube. The user can place its weight at the fitting's own center-of-gravity position and review the effect on the assembled product.

The tool's scope is the longitudinal location along the chosen reference axis. The user remains responsible for representing the actual assembly appropriately and interpreting that location in the context of the proposed handling arrangement.

## Tube Load Analyzer

The objective of Tube Load Analyzer is to examine a tube under a specified loading arrangement with two fully fixed supports. It helps the user review the entered support locations and applied loads, identify critical locations and compare alternative cases that fit that support model.

The user supplies the tube dimensions, support positions, material stiffness and relevant loads. Additional point and distributed loads can be entered to represent the case being investigated. The interface also accommodates loads associated with fittings beyond a tube end.

Typical reasons for using this tool include the following.

- Review a proposed tube loading case using the specified fixed-support arrangement.
- Explore the effect of changing a support location or the location of an applied load.
- Account for tube self-weight and additional attached or applied loads in one organized case.
- Identify locations that deserve closer review when developing a support or handling arrangement.
- Keep the case's geometry, loading diagram and results together for discussion.
- Export chart data for comparison with another case or an independent engineering check.

For example, a user may need to compare two positions for an added fitting while keeping the same tube and support arrangement. The calculator provides a working model in which the fitting's load position can be revised and the resulting case reviewed.

The user should choose this calculator when its two fixed supports represent the intended restraint arrangement. Its purpose is to support a clearly specified tube case within that scope.

## Shipping Frame Load Analyzer

The objective of Shipping Frame Load Analyzer is to help users develop and review a shipping frame arrangement around a coil package. It provides a place to describe the beam layers, coils, rods, lifting points and additional features that define the working design.

Users can build the arrangement progressively, enter section details for each member and use the visual views to inspect the model. The custom section sketcher supports cases that require a user-defined outline. The Design, Loading, Material and Analysis tabs organize the information needed to continue refining the frame.

Typical reasons for using this tool include the following.

- Build a frame model from the dimensions and arrangement of a particular coil package.
- Organize member geometry and placement in a common coordinate system.
- Review the locations of coils, threaded rods, lifting points and welded blocks.
- Inspect member sections and the modeled coil seating arrangement.
- Evaluate changes to member sizes, component placement or loading assumptions.
- Compare alternative frame concepts using consistently recorded inputs.
- Save a frame design, reopen it later and continue its development.
- Provide diagrams and exported data to support an engineering review of the proposed arrangement.

For example, a user may build an initial frame around the coil positions, review the resulting case, and then revise a member section or rod location. Saving the frame before the revision preserves a baseline that can be reopened for comparison.

The current working model represents one frame design with the package-loading information entered for that case. When separate physical frames have different arrangements, the user can prepare separate saved designs and enter the appropriate loading for each.

## A typical work session

1. Open the app and acknowledge the homepage disclaimer.
2. Select the calculator that matches the question being investigated.
3. Enter the known geometry, weights, loads and arrangement information using the units displayed beside the fields.
4. Review the schematic as the model develops and complete the required inputs.
5. Use the calculator's result views and Calculate or refresh control as appropriate for that tool.
6. Review the case, record the relevant information and make deliberate revisions where needed.
7. Select **← Home** to use another calculator or return to the main selection screen.
8. Export the available result data or save the shipping frame design when a record is needed beyond the session.

The input labels use inches for geometry, pound-force for weights and loads, and psi for relevant material or stress quantities. Users should keep their source information consistent with the units shown in the selected calculator.

Each calculator retains its existing initial values and input controls. Some fields begin empty and some have supplied defaults. Enter the project values needed to describe the intended case before relying on its results.

## Homepage disclaimer

The engineering calculation disclaimer appears on the homepage when a new app session begins. The user reads the notice and selects **OK** to access the calculators.

Acknowledgement applies to the combined app for that session. Returning Home, reopening a calculator, loading a frame example or using a calculator's Reset controls retains that acknowledgement. Shipping Frame Load Analyzer opens directly after the user has acknowledged the homepage notice.

The notice states that results depend on the inputs and assumptions, that software and modeling limitations can affect accuracy, and that the user should independently verify the model and results before use in fabrication. The detailed notice is displayed in the app.

## Session continuity and saved work

Input retention is tied to the active browser session. Moving between the homepage and calculators preserves the working entries. The frame sketcher also retains its unfinished drawing and field entries during navigation within that session.

A page refresh, closing the session or restarting the app server can start a fresh session. A new session displays the disclaimer again and initializes the calculators as new working models. Keep a saved record of work that needs to be available later.

The available outputs serve different purposes.

| Output | Purpose |
| --- | --- |
| Coil Center of Gravity CSV | Keep the component and assembly results available for review or spreadsheet work. |
| Tube Load Analyzer CSV | Keep the plotted response data for comparison and reporting. |
| Shipping frame chart and force CSV files | Keep the selected analysis results for review outside the app. |
| Shipping frame design JSON | Preserve the frame's input model for loading and further editing. |

The shipping frame JSON is the app's reopenable design format. CSV exports provide result records. For the tube and center-of-gravity tools, keep the source dimensions and load information needed to recreate a case in a later session.

## Launching the app

Use **app.py** as the entry point for the combined application.

For a local installation, use Python 3.11 or newer and open a terminal in the folder containing `app.py`. Install the dependencies, then start Streamlit.

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

On Windows, `run_app.bat` provides another way to start the app after the dependencies are installed. Keep the process running while using the browser interface.

For a GitHub-backed Streamlit Community Cloud deployment, select the repository and branch containing the app and choose `app.py` as the main file. Keep the Python modules, `requirements.txt` and `assets` folder together at the application root. The `.streamlit/config.toml` file supplies the theme and interface configuration.

## Repository contents

| File or folder | Purpose in the project |
| --- | --- |
| `app.py` | Homepage, session disclaimer and navigation between calculators. |
| `tube_cg_calculator.py` | Coil Center of Gravity interface and supporting functionality. |
| `beam_stress_calculator.py` | Tube Load Analyzer interface and supporting functionality. |
| `shipping_frame_calculator.py` | Shipping Frame Load Analyzer interface. |
| `frame_*.py` | Shipping frame models, geometry, analysis, visuals and result presentation. |
| `assets/` | Homepage graphics and styling, navigation styling and custom section editor. |
| `requirements.txt` | Python dependencies for running the application. |
| `.streamlit/config.toml` | Shared appearance and Streamlit configuration. |
| `run_app.bat` | Windows launcher. |
| `docs/` | Separate calculator guides available with the full source package. |
| `examples/` | Editable shipping frame JSON examples. |
| `tests/` | Checks for calculator behavior, navigation and the section editor. |
| `verification/` | Verification records supplied with the original frame implementation. |

The runtime uses the Python modules and assets directly. The guides, example files and development checks provide additional material for users who want to review or maintain the project.

## Maintenance checks

The tests exercise the calculator behavior and the navigation that keeps each tool's inputs independent. They also check that the homepage disclaimer appears at the start of a session and stays acknowledged while the user moves through the app.

To run the Python checks from the application folder, install pytest and run the test suite.

```sh
python -m pip install pytest
python -m pytest tests
```

The section editor has additional JavaScript checks. Run `npm install` and `npm test` inside the `tests` folder to execute them with Node.js.
