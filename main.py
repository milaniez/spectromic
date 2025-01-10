import sounddevice as sd
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import simpledialog
from datetime import datetime, timedelta
import multiprocessing as mp

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

# Function to select a sample rate using a dialog
def get_sample_rate(device_id):
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    selected_rate = simpledialog.askinteger("Type in a Sample Rate", "Type in an integer")
    try:
        sd.check_input_settings(device=device_id, samplerate=selected_rate)
    except Exception:
        return None
    return selected_rate

# Function to capture audio in a separate process
def audio_capture_process(queue, device_id, sample_rate, blocksize):
    adc_time_offset = None

    def audio_callback(indata, frames, time, status):
        current_time = datetime.now().timestamp()
        nonlocal adc_time_offset
        if status:
            print(status)

        adc_time = time.inputBufferAdcTime
        if adc_time_offset is None:
            adc_time_offset = current_time - time.currentTime - (blocksize - 1) / sample_rate

        adjusted_adc_time = adc_time + adc_time_offset
        print(f"ADC Time: {adjusted_adc_time}, Current Time: {current_time}, Offset: {adc_time_offset}, Input Buffer Time: {time.inputBufferAdcTime}, Current Time: {time.currentTime}, Frames: {frames}")
        queue.put((indata.copy(), adjusted_adc_time))

    with sd.InputStream(device=device_id, channels=1, samplerate=sample_rate, blocksize=blocksize, callback=audio_callback):
        while True:
            pass

# Function to start the live spectrogram
def start_spectrogram(queue, sample_rate):
    plt.ion()
    fig, ax = plt.subplots()
    time_window = 10  # Display the last 10 seconds
    y = np.linspace(0, sample_rate // 2, 400)
    Z = np.zeros((400, time_window * 100))

    img = ax.imshow(Z, aspect='auto', origin='lower', extent=[0, time_window, 0, sample_rate // 2], cmap='magma')
    plt.colorbar(img)
    ax.set_xlabel('Time')
    ax.set_ylabel('Frequency (Hz)')

    while True:
        try:
            data, adjusted_time = queue.get()
            spectrum = np.abs(np.fft.rfft(data[:, 0]))
            spectrum = np.interp(np.linspace(0, len(spectrum), 400), np.arange(len(spectrum)), spectrum)
            Z[:, :-1] = Z[:, 1:]
            Z[:, -1] = spectrum

            # Update the x-axis to show real local time
            current_time = datetime.fromtimestamp(adjusted_time)
            time_labels = [(current_time - timedelta(seconds=time_window - i)).strftime("%H:%M:%S") for i in range(time_window)]
            ax.set_xticks(np.linspace(0, time_window, len(time_labels)))
            ax.set_xticklabels(time_labels, rotation=45)

            img.set_data(Z)
            plt.pause(0.01)
        except KeyboardInterrupt:
            break

if __name__ == "__main__":
    devices = list_audio_devices()
    if not devices:
        print("No input devices found.")
        exit(1)
    selected_device_id = None
    while selected_device_id is None:
        selected_device_id = select_device(devices)
    selected_sample_rate = None
    while selected_sample_rate is None:
        selected_sample_rate = get_sample_rate(selected_device_id)

    blocksize = None
    while blocksize is None or blocksize <= 10 or blocksize > selected_sample_rate:
        blocksize = simpledialog.askinteger("Blocksize", "Enter blocksize (samples per block):", initialvalue=1024)

    print(f"Selected Device: {devices[selected_device_id]['name']} with index {selected_device_id}")
    print(f"Selected Sample Rate: {selected_sample_rate} Hz")
    print(f"Selected Blocksize: {blocksize} samples")

    audio_queue = mp.Queue()
    audio_process = mp.Process(target=audio_capture_process, args=(audio_queue, selected_device_id, selected_sample_rate, blocksize))
    audio_process.start()

    start_spectrogram(audio_queue, selected_sample_rate)

    audio_process.join()
