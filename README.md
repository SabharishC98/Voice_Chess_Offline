# 🎙️ Offline Voice Chess

A fully offline chess game with voice command support, powered by Python, Pygame, and Vosk speech recognition. Play chess by speaking your moves naturally!

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ Features

- 🎮 **Full Chess Engine**: Complete chess implementation with all legal move validation
- 🎤 **Offline Voice Recognition**: No internet required - uses Vosk for local speech processing
- 🔊 **Natural Language Commands**: Speak moves in various formats (e.g., "knight to f3", "e4", "castle kingside")
- 📊 **Real-time Audio Visualization**: See your microphone input levels
- ✅ **Move Confirmation**: Review and confirm moves before execution
- 🎨 **Clean GUI**: Visual chessboard with coordinate labels and move highlighting
- 🌍 **Accent Support**: Enhanced recognition for various accents and pronunciations

## 🚀 Quick Start

### Prerequisites

- Python 3.7 or higher
- Microphone for voice input
- Windows/Linux/Mac OS

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/offline-voice-chess.git
cd offline-voice-chess
```

2. **Install dependencies**
```bash
pip install pygame chess numpy vosk pyaudio
```

3. **Download Vosk Speech Model**
   - Visit [Vosk Models](https://alphacephei.com/vosk/models)
   - Download `vosk-model-en-us-0.22` (or another English model)
   - Extract the model to your project directory
   - Update the model path in `second.py`:
   ```python
   model_path = r"path/to/vosk-model-en-us-0.22"
   ```

4. **Add Chess Piece Images** (Optional)
   - Create an `images` folder in your project directory
   - Add PNG images for chess pieces named as:
     - `wp.png`, `wn.png`, `wb.png`, etc.
     - `bp.png`, `bn.png`, `bb.png`, etc.
   - If images are missing, the game will display text-based pieces

5. **Run the game**
```bash
python second.py
```

## 🎮 How to Play

### Keyboard Controls

- **SPACE**: Start listening for voice command
- **Y**: Confirm the suggested move
- **N**: Reject the suggested move
- **H**: Toggle help overlay
- **ESC**: Quit game

### Voice Commands

The game accepts various natural language formats:

#### Standard Notation
- `"e4"` - Move pawn to e4
- `"Nf3"` - Move knight to f3
- `"Qd4"` - Move queen to d4

#### Natural Language
- `"knight to f3"`
- `"queen to d4"`
- `"pawn to e4"`

#### Coordinate Pairs
- `"e2 to e4"`
- `"g1 to f3"`

#### Special Moves
- `"castle"` or `"castle kingside"` - Short castle (O-O)
- `"castle queenside"` or `"long castle"` - Long castle (O-O-O)

### Tips for Better Recognition

✅ **Do:**
- Speak clearly at normal pace
- Use standard chess notation when possible
- Watch the green audio level bar (speak loud enough)
- Wait for the listening indicator before speaking
- Confirm moves before they execute

❌ **Don't:**
- Rush through your command
- Speak too quietly or too loudly
- Try to speak while the game is processing
- Use ambiguous phrases for moves

## 🔧 Configuration

### Audio Settings

Adjust these constants in `second.py` for optimal performance:

```python
MAX_LISTEN_TIME = 5.0      # Maximum listening duration (seconds)
SILENCE_THRESHOLD = 100    # Audio level threshold for detecting speech
SILENCE_DURATION = 1.0     # Silence duration before finalizing (seconds)
DEBUG = True               # Enable detailed logging
```

### Improving Recognition

The game includes extensive accent support and phonetic mappings. If certain words aren't recognized:

1. Check the console output with `DEBUG = True`
2. Add your pronunciation variants to the `letter_map` and `number_map` dictionaries in `preprocess_speech_input()`
3. Test and adjust the `SILENCE_THRESHOLD` based on your microphone

## 🏗️ Project Structure

```
offline-voice-chess/
├── second.py              # Main game file
├── images/                # Chess piece images (optional)
│   ├── wp.png
│   ├── bk.png
│   └── ...
├── vosk-model-en-us-0.22/ # Vosk speech model
└── README.md
```

## 🐛 Troubleshooting

### Voice Recognition Not Working

1. **Check microphone permissions**: Ensure Python has access to your microphone
2. **Verify model path**: Make sure the Vosk model path is correct
3. **Test microphone**: The green audio level bar should show activity when you speak
4. **Adjust thresholds**: Modify `SILENCE_THRESHOLD` if speech isn't detected

### Moves Not Recognized

1. **Enable debug mode**: Set `DEBUG = True` to see recognition details
2. **Check legal moves**: The console shows all available legal moves
3. **Try different formats**: Use coordinate notation (e.g., "e2 e4") instead of natural language
4. **Speak piece names clearly**: "Knight" works better than "night"

### Performance Issues

1. **Close unnecessary applications**: Free up CPU resources
2. **Use smaller Vosk model**: Download `vosk-model-small-en-us-0.15` for faster processing
3. **Reduce frame rate**: Modify `clock.tick(30)` to a lower value

## 🤝 Contributing

Contributions are welcome! Here are some ways you can help:

- 🐛 Report bugs and issues
- 💡 Suggest new features
- 🌍 Add support for more languages
- 🎨 Improve the UI/UX
- 📝 Enhance documentation

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes and test thoroughly
4. Commit your changes: `git commit -m "Add feature"`
5. Push to your fork: `git push origin feature-name`
6. Create a Pull Request

## 📋 Known Issues

- Letters 'n', 'r', 'q', 'k' can sometimes be misrecognized (improvements in progress)
- Pawn promotion currently defaults to queen
- Some accents may require additional tuning

## 🔮 Future Enhancements

- [ ] AI opponent integration
- [ ] Move history and undo functionality
- [ ] Save/load game state
- [ ] Multiple language support
- [ ] Online multiplayer
- [ ] Advanced pawn promotion selection
- [ ] Opening book suggestions
- [ ] Game analysis and statistics

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Python Chess](https://python-chess.readthedocs.io/) - Chess logic library
- [Vosk](https://alphacephei.com/vosk/) - Offline speech recognition
- [Pygame](https://www.pygame.org/) - Game development framework
- Chess piece images from [Various sources]

## 📧 Contact

Have questions or suggestions? Feel free to:
- Open an issue
- Submit a pull request
- Contact: [sabharishc98@example.com]

---

⭐ **If you enjoy this project, please give it a star!** ⭐

Made with ❤️ by [Sabharish C]
