package app.bridge;
import com.chaquo.python.Python;
import com.chaquo.python.PyObject;
import java.util.concurrent.*;
final class Backend {
 static final ExecutorService work = Executors.newSingleThreadExecutor();
 static PyObject module() { return Python.getInstance().getModule("mobile"); }
}
