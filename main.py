import sounddevice as sd
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta
import multiprocessing as mp
import queue as threading_queue

# Function to list all available input devices
def list_audio_devices():
    devices = sd.query_devices()
    input_devices = [d for d in devices if d['max_input_channels'] > 0]
    return input_devices

# Function to display a single dialog to select device, sample rate, and block size
def get_audio_settings(devices):
    def on_submit():
        selected_device.set(device_menu.get())
        selected_sample_rate.set(sample_rate_entry.get())
        selected_block_size.set(block_size_entry.get())
        root.destroy()

    root = tk.Tk()
    root.title("Audio Settings")

    # Dropdown for audio device selection
    tk.Label(root, text="Select Audio Device:").grid(row=0, column=0)
    device_names = [f"{i}: {d['name']}" for i, d in enumerate(devices)]
    selected_device = tk.StringVar(value=device_names[0])
    device_menu = ttk.Combobox(root, textvariable=selected_device, values=device_names)
    device_menu.grid(row=0, column=1)

    # Entry for sample rate
    tk.Label(root, text="Sample Rate:").grid(row=1, column=0)
    selected_sample_rate = tk.StringVar(value="48000")
    sample_rate_entry = tk.Entry(root, textvariable=selected_sample_rate)
    sample_rate_entry.grid(row=1, column=1)

    # Entry for block size
    tk.Label(root, text="Block Size:").grid(row=2, column=0)
    selected_block_size = tk.StringVar(value="1200")
    block_size_entry = tk.Entry(root, textvariable=selected_block_size)
    block_size_entry.grid(row=2, column=1)

    # Submit button
    submit_button = tk.Button(root, text="Submit", command=on_submit)
    submit_button.grid(row=3, columnspan=2)

    root.mainloop()

    return int(selected_device.get().split(':')[0]), int(selected_sample_rate.get()), int(selected_block_size.get())

# Function to capture audio in a separate process
def audio_capture_process(out_queue, device_id, sample_rate, blocksize):
    internal_queue = threading_queue.Queue()
    adc_time_offset = None

    def audio_callback(indata, frames, time, status):
        current_time = datetime.now().timestamp()
        nonlocal adc_time_offset
        if status:
            print(status)

        adc_time = time.inputBufferAdcTime
        if adc_time_offset is None:
            adc_time_offset = current_time - adc_time

        adjusted_adc_time = adc_time + adc_time_offset
        print(f"ADC Time: {adjusted_adc_time}, Current Time: {current_time}, Offset: {adc_time_offset}, Input Buffer Time: {time.inputBufferAdcTime}, Current Time: {time.currentTime}")
        internal_queue.put((indata.copy(), adjusted_adc_time))

    def send_data():
        while True:
            try:
                data, adjusted_time = internal_queue.get()
                out_queue.put((data, adjusted_time))
            except Exception as e:
                print(f"Error in sending data: {e}")
                break

    with sd.InputStream(device=device_id, channels=1, samplerate=sample_rate, blocksize=blocksize, callback=audio_callback):
        send_data()

# Function to start the live spectrogram
def start_spectrogram(queue, sample_rate, block_size):
    expected_spectrum_len = block_size // 2 + 1
    plt.ion()
    fig, ax = plt.subplots()
    time_window = 10  # Display the last 10 seconds
    Z = np.zeros((expected_spectrum_len, time_window * 100))

    img = ax.imshow(Z, aspect='auto', origin='lower', extent=[0, time_window, 0, sample_rate // 2], cmap='magma')
    plt.colorbar(img)
    ax.set_xlabel('Time')
    ax.set_ylabel('Frequency (Hz)')

    try:
        while plt.fignum_exists(fig.number):
            while not queue.empty():
                data, adjusted_time = queue.get()
                spectrum = np.abs(np.fft.rfft(data[:, 0]))
                print(f"data len: {len(data)}, spectrum len: {len(spectrum)}")
                Z[:, :-1] = Z[:, 1:]
                Z[:, -1] = spectrum

                print(f"Z shape: {Z.shape}")

                # Update the x-axis to show real local time
                current_time = datetime.fromtimestamp(adjusted_time)
                time_labels = [(current_time - timedelta(seconds=time_window - i)).strftime("%H:%M:%S") for i in range(time_window)]
                ax.set_xticks(np.linspace(0, time_window, len(time_labels)))
                ax.set_xticklabels(time_labels, rotation=45)

                img.set_data(Z)
            plt.pause(0.01)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error: {e}")
    finally:
        plt.close()

if __name__ == "__main__":
    devices = list_audio_devices()
    if not devices:
        print("No input devices found.")
        exit(1)

    selected_device_id, selected_sample_rate, blocksize = get_audio_settings(devices)

    print(f"Selected Device: {devices[selected_device_id]['name']} at index {selected_device_id}")
    print(f"Selected Sample Rate: {selected_sample_rate}")
    print(f"Selected Block Size: {blocksize}")

    audio_queue = mp.Queue()
    audio_process = mp.Process(target=audio_capture_process, args=(audio_queue, selected_device_id, selected_sample_rate, blocksize))
    audio_process.daemon = True
    audio_process.start()

    start_spectrogram(audio_queue, selected_sample_rate, blocksize)
