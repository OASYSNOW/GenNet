# GenNet
## Framework for Interpretable Neural Networks
[The bioRxive paper](https://www.biorxiv.org/content/10.1101/2020.06.19.159152v1)

Find the demo here: https://tinyurl.com/y8hh8rul

## Prerequisites:


- GenNet has been tested with an NVIDIA GPU with:

  * Cuda  9.1 & Tensorflow 1.12.0 
  * Cuda 10.1 & Tensorflow 1.13.1

- [HASE](https://github.com/roshchupkin/hase) is used for the conversion of the data to .h5 for parallel reading and writing.

- [Annovar](https://doc-openbio.readthedocs.io/projects/annovar/en/latest/) for obtaining gene annotations

### Clone the repository

Open terminal. Navigate to the a place where you want to store the project. Clone the repository:
```
git clone https://github.com/arnovanhilten/GenNet
```
### Install the virtual envionment

**Navigate to the home folder and create a virtual environment**
```
cd ~
python3 -m venv env_GenNet
```

**Activate the environment**
```
source env_GenNet/bin/activate
```

**Install the packages**
```
pip3 install --upgrade pip
pip3 install -r requirements_GenNet.txt
```
**Start jupyter notebook:**

```
jupyter notebook
