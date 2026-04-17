# RAColony
# ColonyAnalyzer

🎯 Quick Start

Because the software will automatically decompress the deep learning model file for the first time, it may take a long time. Please wait patiently.

Launch Application - Double-click ColonyAnalyzer.exe

Load Image - Click "Select Image" and choose your culture dish photo

Set ROI - Left-click on dish center, scroll wheel to adjust radius

Select Dish Type - Choose appropriate culture medium type

Start Analysis - Click "Start Analysis" and wait for results



📊 Test with Sample Data
Download Sample Images
Sample images are available in the MacroImageData directory:

📖 Usage Guide
Step 1: Image Selection
Supported formats: PNG, JPG, JPEG, BMP, TIFF

text
Recommended image specifications:
- Resolution: 2000-5000 pixels
- Format: Color (RGB)
- File size: < 50 MB


Step 2: ROI Setting
Action	Effect
Left Click	Set circle center
Scroll Wheel	Adjust radius (±20 px)
Drag (while pressing)	Move circle center
Slider	Fine-tune radius value


Step 3: Parameter Configuration
Parameter	Options	Description
Dish Type	GAM (1), PYG (2), YCFA (3), MS (4)	Culture medium type
Dish Range	0-5000 px	Expected dish diameter


Step 4: Analysis Execution
Click "Start Analysis" to begin colony detection:

Image Enhancement - Contrast adjustment (1-2 seconds)

Dish Detection - Circle detection and masking (2-3 seconds)

Colony Detection - Otsu thresholding and contour extraction (5-10 seconds)

Adherent Split - CellPose segmentation (10-30 seconds, optional)

Result Generation - Annotated image and JSON output


Output Files
File	Description
result_MMDDHHMMSS.jpg	Annotated image with colony numbers
results/ directory	All result images are saved here


Performance Metrics
Step	Time (typical)	Accuracy
Image loading	< 0.5 sec	100%
ROI processing	< 0.1 sec	-
Colony detection	5-10 sec	> 95%
Adherent split	10-30 sec	> 85%
Total analysis	15-40 sec	> 90%


💻 System Requirements
Minimum Requirements
Component	Requirement
OS	Windows 10/11 (64-bit)
CPU	Intel Core i5 or equivalent
RAM	8 GB
Storage	500 MB free space
Display	1366×768 resolution


Recommended Requirements
Component	Requirement
OS	Windows 10/11 (64-bit)
CPU	Intel Core i7 or equivalent
RAM	16 GB
GPU	NVIDIA GTX 1060+ (for CellPose)
Storage	1 GB free space
Display	1920×1080 resolution


Common Issues
Issue	Solution
Model loading failed	Continue without CellPose (simplified mode)
Slow analysis	Reduce image resolution or use GPU
ROI not detected	Ensure clear dish boundary in image
No colonies found	Adjust ROI radius or check lighting
Permission denied	Run as administrator


Error Codes
Code	Meaning	Solution
-1	Dish range not detected	Adjust ROI radius
-2	Lighting condition unqualified	Improve image lighting
1	Success	-



# RAColonyDuplicateRemovalAnalysisSystem


📊 Test with Sample Data
Download Sample Data
Sample datasets are available in the FeatureData directory:

📖 Usage Guide
Step 1: Prepare Your Data
Your Excel file should contain:

For Raman mode: Columns 0-749 (spectral data)

For Image mode: Columns Feature1-Feature20 (morphological features)

Step 2: Launch Application

Step 3: Configure Analysis
Select File: Click "Browse" to choose your Excel file

Choose Analysis Type:

Raman Features for spectral data

Image Features for morphological data

Set Pick Count:

Enter specific number, or

Check "Auto Calculate Pick Count" for automatic determination

Start Analysis: Click "Start Analysis" button

Step 4: Interpret Results
Gray dots: All samples in the dataset

Red dots: Selected samples after duplicate removal

Interactive features:

Use scroll wheel to zoom

Drag scroll bars to pan

Click "Save Figure" to export the visualization

📊 Input/Output Specifications
Input Format
Column Type	Column Names	Description
Raman	0, 1, 2, ..., 749	Spectral intensity values
Image	Feature1, Feature2, ..., Feature20	Morphological features


❓ FAQ
Q: Why are my results different each time?
A:  Greedy iteration strategy is applied to search for the optimal solution, but because some sample features 
are too close, there may be small differences in the selected points, but almost no impact on species coverage 

Q: How long does analysis take?
A: For 1000 samples with 20 features, analysis typically completes in 10-30 seconds.

Q: Can I process multiple files?
A: Currently processes one file at a time. Batch processing coming in future updates.

Q: What if my data has missing values?
A: The application automatically fills missing values with 0 and removes non-numeric columns.


🐛 Troubleshooting
Common Issues and Solutions
Issue	Solution
"No numeric data columns found"	Ensure your Excel contains numerical data only
Application freezes during analysis	Use smaller dataset or increase RAM
