import sounddevice as sd
import matplotlib.pyplot as plt
import numpy as np
import queue
import tkinter as tk
from tkinter import simpledialog

# Function to list all available input devices
def list_audio_devices():
    devices = sd.query_devices()
    input_devices = [d for d in devices if d['max_input_channels'] > 0]
    return input_devices

# Function to select an audio device using a dialog
def select_device(devices):
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    device_names = [f"{i}: {d['name']}" for i, d in enumerate(devices)]
    selected_device = simpledialog.askstring("Select Device", "\n".join(device_names))
    if selected_device is not None:
        try:
            return int(selected_device.split(':')[0])
        except ValueError:
            return None
    return None

# Queue to hold audio data
audio_queue = queue.Queue()

# Callback function to put audio data into the queue
def audio_callback(indata, frames, time, status):
    if status:
        print(status)
    audio_queue.put(indata.copy())

# Function to start the live spectrogram
def start_spectrogram(device_id):
    plt.ion()
    fig, ax = plt.subplots()
    x = np.linspace(0, 1, 100)
    y = np.linspace(0, 8000, 400)
    X, Y = np.meshgrid(x, y)
    Z = np.zeros_like(X)

    img = ax.imshow(Z, aspect='auto', origin='lower', extent=[0, 1, 0, 8000], cmap='magma')
    plt.colorbar(img)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Frequency (Hz)')

    with sd.InputStream(device=device_id, channels=1, callback=audio_callback):
        while True:
            try:
                data = audio_queue.get()
                spectrum = np.abs(np.fft.rfft(data[:, 0]))
                spectrum = np.interp(np.linspace(0, len(spectrum), 400), np.arange(len(spectrum)), spectrum)
                Z[:, :-1] = Z[:, 1:]
                print("spectrum length", len(spectrum))
                Z[:, -1] = spectrum[:400]
                img.set_data(Z)
                plt.pause(0.01)
            except KeyboardInterrupt:
                break

if __name__ == "__main__":
    devices = list_audio_devices()
    if not devices:
        print("No input devices found.")
    else:
        selected_device_id = select_device(devices)
        if selected_device_id is not None:
            start_spectrogram(selected_device_id)
        else:
            print("No device selected.")
